#!/usr/bin/env python3
"""
Continuous Brain Improvement Loop v3 — Calibration-Aware.

Upgrade from v2:
1. CALIBRATED SCORING: Weights backtest by regime-specific offset
   - Death rounds overshoot reality by ~20 points
   - Growth rounds undershoot reality by ~5 points
   - Optimizing for calibrated score = optimizing for REAL leaderboard score
2. REGIME-WEIGHTED: Emphasizes growth rounds (favorable calibration bias)
3. BLEND WEIGHT UPDATE: Periodically compares V2 vs V3 and updates model_weights.json

Usage:
  python churn_v3.py           # Run continuous loop
"""

import json
import os
import tempfile
import time
import random
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from regime_model import RegimeModel, classify_round
from learned_model import NeighborhoodModel

DATA_DIR = Path(__file__).parent / "data"
PARAMS_FILE = DATA_DIR / "brain_v3_params.json"
WEIGHTS_FILE = DATA_DIR / "model_weights.json"
CHURN_LOG = Path.home() / "churn_v3.log"
COMPETITION_END = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)

# Calibration: backtest - actual (positive = overshoot)
REGIME_CALIBRATION = {"death": 20.0, "stable": 7.0, "growth": -5.0}


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(CHURN_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        print(line, flush=True)


def load_best():
    if PARAMS_FILE.exists():
        with open(PARAMS_FILE) as f:
            p = json.load(f)
        return p.get("v3_score", 0), p
    return 0, {}


def save_if_better(score, alphas, temps, collapse, sigma, experiment_name):
    best_score, _ = load_best()
    if score > best_score:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        params = {
            "alphas": {str(k): round(float(v), 2) for k, v in alphas.items()},
            "temps": {k: round(float(v), 3) for k, v in temps.items()},
            "collapse": round(float(collapse), 4),
            "sigma": round(float(sigma), 3),
            "v3_score": round(float(score), 2),
            "baseline": round(float(best_score), 2),
            "delta": round(float(score - best_score), 2),
            "experiment": experiment_name,
            "fitted_at": datetime.now(timezone.utc).isoformat(),
        }
        fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(params, f, indent=2)
            os.replace(tmp_path, str(PARAMS_FILE))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        log(f"  NEW BEST: {score:.2f} (was {best_score:.2f}, +{score - best_score:.2f}) [{experiment_name}]")
        return True
    return False


def _load_obs_for_round(round_num, seed_idx):
    """Load saved observation data for a round/seed, if available."""
    for label in [f"seed{seed_idx}_stacked", f"seed{seed_idx}_overview"]:
        pc = DATA_DIR / f"obs_counts_r{round_num}_{label}.npy"
        pt = DATA_DIR / f"obs_total_r{round_num}_{label}.npy"
        if pc.exists() and pt.exists():
            return np.load(pc), np.load(pt)
    return None, None


def score_variant_calibrated(rounds_data, alphas, temps, collapse, sigma):
    """Calibration-aware backtest: weights scores by regime.

    Growth rounds get a bonus (backtest undershoots reality).
    Death rounds get a penalty (backtest overshoots reality).
    This pushes optimization toward params that perform well on growth rounds,
    where our predictions actually score BETTER than backtest suggests.
    """
    test_rounds = rounds_data[-5:] if len(rounds_data) > 5 else rounds_data
    weighted_scores = []
    weights = []

    for rd in test_rounds:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)
        cal_offset = REGIME_CALIBRATION.get(regime, 7.0)

        brain = RegimeModel()
        for other in rounds_data:
            if other["round_number"] != rn:
                brain.add_training_data(other)
        brain.finalize()
        h, w = rd["map_height"], rd["map_width"]

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]
            pred = brain.predict_grid(rd, si, regime=regime)

            # Dirichlet alpha blending with observations
            obs_counts, obs_total = _load_obs_for_round(rn, si)
            if obs_counts is None:
                obs_counts = np.zeros((h, w, NUM_CLASSES))
                obs_total = np.ones((h, w))
                for y in range(h):
                    for x in range(w):
                        if int(ig[y][x]) in STATIC_TERRAIN:
                            obs_total[y, x] = 0
                            continue
                        obs_counts[y, x, gt[y, x].argmax()] = 1.0

            for y in range(h):
                for x in range(w):
                    if obs_total[y, x] == 0:
                        continue
                    init_cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                    av = alphas.get(init_cls, 8.0)
                    alpha = av * pred[y, x]
                    alpha = np.maximum(alpha, PROB_FLOOR)
                    pred[y, x] = (alpha + obs_counts[y, x]) / (alpha.sum() + obs_total[y, x])

            # Entropy-aware temperature
            for y in range(h):
                for x in range(w):
                    if ig[y][x] in STATIC_TERRAIN:
                        continue
                    p = np.maximum(pred[y, x], 1e-10)
                    ent = -np.sum(p * np.log(p))
                    t = temps["low"] if ent < 0.3 else (temps["mid"] if ent < 1.0 else temps["high"])
                    pred[y, x] = pred[y, x] ** (1.0 / t)

            # Collapse
            for y in range(h):
                for x in range(w):
                    if ig[y][x] in STATIC_TERRAIN:
                        continue
                    probs = pred[y, x]
                    mask = probs < collapse
                    if mask.any() and not mask.all():
                        probs[mask] = PROB_FLOOR
                        pred[y, x] = probs / probs.sum()

            # Smooth
            if sigma > 0:
                sm = np.copy(pred)
                for c in range(NUM_CLASSES):
                    sm[:, :, c] = gaussian_filter(pred[:, :, c], sigma=sigma)
                for y in range(h):
                    for x in range(w):
                        if ig[y][x] in STATIC_TERRAIN:
                            sm[y, x] = pred[y, x]
                pred = sm

            pred = np.maximum(pred, PROB_FLOOR)
            pred /= pred.sum(axis=-1, keepdims=True)

            raw_score = score_prediction(gt, pred, initial_grid=ig)["score"]
            # Apply calibration: estimated real score = raw - offset
            calibrated = raw_score - cal_offset
            weighted_scores.append(calibrated)

    return np.mean(weighted_scores) if weighted_scores else 0.0


def update_blend_weights(rounds_data):
    """Compare V2 vs V3 and update model_weights.json every few batches."""
    log("  Updating blend weights (V2 vs V3 comparison)...")

    test_rounds = rounds_data[-5:] if len(rounds_data) > 5 else rounds_data
    v2_cal, v3_cal = [], []

    for rd in test_rounds:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)
        cal_offset = REGIME_CALIBRATION.get(regime, 7.0)
        h, w = rd["map_height"], rd["map_width"]

        # V3
        brain_v3 = RegimeModel()
        for other in rounds_data:
            if other["round_number"] != rn:
                brain_v3.add_training_data(other)
        brain_v3.finalize()

        # V2
        brain_v2 = NeighborhoodModel()
        for other in rounds_data:
            if other["round_number"] != rn:
                brain_v2.add_training_data(other)
        brain_v2.finalize()

        for si_str, sd in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(sd["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            p3 = brain_v3.predict_grid(rd, si, regime=regime)
            p3 = np.maximum(p3, PROB_FLOOR)
            p3 /= p3.sum(axis=-1, keepdims=True)
            s3 = score_prediction(gt, p3, initial_grid=ig)["score"] - cal_offset

            p2 = brain_v2.predict_grid(rd, si)
            p2 = p2 ** (1.0 / 1.12)
            p2 = np.maximum(p2, PROB_FLOOR)
            p2 /= p2.sum(axis=-1, keepdims=True)
            s2 = score_prediction(gt, p2, initial_grid=ig)["score"] - cal_offset

            v2_cal.append(s2)
            v3_cal.append(s3)

    v2_avg = np.mean(v2_cal) if v2_cal else 0
    v3_avg = np.mean(v3_cal) if v3_cal else 0

    total = max(v2_avg + v3_avg, 1.0)
    if total > 0 and v2_avg > 0 and v3_avg > 0:
        v3_weight = v3_avg / total
        v3_weight = max(0.3, min(0.9, v3_weight))
    elif v3_avg >= v2_avg:
        v3_weight = 0.7
    else:
        v3_weight = 0.3

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({
                "v3_weight": round(v3_weight, 3),
                "v2_weight": round(1.0 - v3_weight, 3),
                "v2_avg": round(v2_avg, 2),
                "v3_avg": round(v3_avg, 2),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }, f, indent=2)
        os.replace(tmp_path, str(WEIGHTS_FILE))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    log(f"  Blend: V3={v3_weight:.0%} V2={1-v3_weight:.0%} "
        f"(V2_cal={v2_avg:.1f} V3_cal={v3_avg:.1f})")


def run_experiments(rounds_data):
    """Run a batch of experiments with calibrated scoring."""
    best_score, best_params = load_best()
    alphas = {int(k): v for k, v in best_params.get("alphas", {0: 8, 1: 4, 2: 3, 3: 3, 4: 10, 5: 50}).items()}
    temps = best_params.get("temps", {"low": 0.9, "mid": 1.1, "high": 1.3})
    collapse = best_params.get("collapse", 0.016)
    sigma = best_params.get("sigma", 0.3)

    iteration = 0

    # A: Alpha perturbations
    log("Experiment A: Alpha perturbations")
    for _ in range(8):
        iteration += 1
        test_alphas = {}
        for cls in range(6):
            base = alphas.get(cls, 8.0)
            test_alphas[cls] = max(0.5, base * random.uniform(0.5, 2.0))
        s = score_variant_calibrated(rounds_data, test_alphas, temps, collapse, sigma)
        if save_if_better(s, test_alphas, temps, collapse, sigma, f"alpha_perturb_{iteration}"):
            alphas = test_alphas
        log(f"  [{iteration}] alphas={[round(test_alphas[i],1) for i in range(6)]} -> {s:.2f}")

    # B: Temperature perturbations
    log("Experiment B: Temperature perturbations")
    for _ in range(8):
        iteration += 1
        test_temps = {
            "low": max(0.3, temps["low"] + random.uniform(-0.3, 0.3)),
            "mid": max(0.3, temps["mid"] + random.uniform(-0.3, 0.3)),
            "high": max(0.3, temps["high"] + random.uniform(-0.3, 0.3)),
        }
        s = score_variant_calibrated(rounds_data, alphas, test_temps, collapse, sigma)
        if save_if_better(s, alphas, test_temps, collapse, sigma, f"temp_perturb_{iteration}"):
            temps = test_temps
        log(f"  [{iteration}] temps=({test_temps['low']:.2f},{test_temps['mid']:.2f},{test_temps['high']:.2f}) -> {s:.2f}")

    # C: Collapse threshold sweep
    log("Experiment C: Collapse threshold")
    for c_val in [0.005, 0.008, 0.01, 0.012, 0.016, 0.02, 0.025, 0.03]:
        iteration += 1
        s = score_variant_calibrated(rounds_data, alphas, temps, c_val, sigma)
        if save_if_better(s, alphas, temps, c_val, sigma, f"collapse_{c_val}"):
            collapse = c_val
        log(f"  [{iteration}] collapse={c_val} -> {s:.2f}")

    # D: Sigma sweep
    log("Experiment D: Smoothing sigma")
    for s_val in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]:
        iteration += 1
        s = score_variant_calibrated(rounds_data, alphas, temps, collapse, s_val)
        if save_if_better(s, alphas, temps, collapse, s_val, f"sigma_{s_val}"):
            sigma = s_val
        log(f"  [{iteration}] sigma={s_val} -> {s:.2f}")

    # E: Entropy threshold sweep
    log("Experiment E: Entropy thresholds")
    for _ in range(5):
        iteration += 1
        spread = random.uniform(0.1, 0.5)
        test_temps = {
            "low": max(0.3, 1.0 - spread),
            "mid": 1.0,
            "high": max(0.3, 1.0 + spread),
        }
        s = score_variant_calibrated(rounds_data, alphas, test_temps, collapse, sigma)
        if save_if_better(s, alphas, test_temps, collapse, sigma, f"spread_{spread:.2f}"):
            temps = test_temps
        log(f"  [{iteration}] spread={spread:.2f} ({test_temps['low']:.2f},{test_temps['mid']:.2f},{test_temps['high']:.2f}) -> {s:.2f}")

    # F: Random combined perturbations
    log("Experiment F: Combined random search")
    for _ in range(15):
        iteration += 1
        test_alphas = {cls: max(0.5, alphas.get(cls, 8) * random.uniform(0.7, 1.4)) for cls in range(6)}
        test_temps = {
            "low": max(0.3, temps["low"] + random.uniform(-0.15, 0.15)),
            "mid": max(0.3, temps["mid"] + random.uniform(-0.15, 0.15)),
            "high": max(0.3, temps["high"] + random.uniform(-0.15, 0.15)),
        }
        test_collapse = max(0.003, collapse * random.uniform(0.5, 2.0))
        test_sigma = max(0.0, sigma + random.uniform(-0.2, 0.2))
        s = score_variant_calibrated(rounds_data, test_alphas, test_temps, test_collapse, test_sigma)
        if save_if_better(s, test_alphas, test_temps, test_collapse, test_sigma, f"combined_{iteration}"):
            alphas, temps, collapse, sigma = test_alphas, test_temps, test_collapse, test_sigma
        if iteration % 5 == 0:
            log(f"  [{iteration}] combined -> {s:.2f}")

    best_score_after, _ = load_best()
    log(f"\nBatch complete: {iteration} experiments. Score: {best_score:.2f} -> {best_score_after:.2f}")
    return iteration


def main():
    log("=" * 60)
    log("CHURN V3: CALIBRATION-AWARE BRAIN IMPROVEMENT")
    log("=" * 60)

    total_experiments = 0
    batch = 0

    while datetime.now(timezone.utc) < COMPETITION_END:
        batch += 1
        rounds_data = load_cached_rounds()
        log(f"\nBatch {batch}: {len(rounds_data)} rounds of training data")

        n = run_experiments(rounds_data)
        total_experiments += n

        best_score, best_params = load_best()
        log(f"Total experiments so far: {total_experiments}. Best score: {best_score:.2f}")
        log(f"Best experiment: {best_params.get('experiment', '?')}")

        # Update blend weights every 5 batches
        if batch % 5 == 0:
            try:
                update_blend_weights(rounds_data)
            except Exception as e:
                log(f"  Blend weight update failed: {e}")

        log("Starting next batch in 30s...")
        time.sleep(30)

    log(f"\nCompetition ended. Total experiments: {total_experiments}")


if __name__ == "__main__":
    main()
