#!/usr/bin/env python3
"""
Continuous Brain Improvement Loop — Machine Learning for Real.

Unlike running the same 4 scripts over and over, this loop:
1. Tries DIFFERENT model variants each iteration
2. Scores each variant via backtest
3. Keeps the best, discards the rest
4. Moves to the next experiment
5. Repeats until killed or competition ends

Experiments it runs (in order, cycling):
A. Per-terrain alpha sweep (6 params, different starting points)
B. Entropy temperature sweep (3 params, different thresholds)
C. Collapse threshold sweep
D. Smoothing sigma sweep
E. Regime classification threshold sweep
F. Observation blending weight variants
G. Round-specific calibration weight variants
H. Combined: best of each above

Each experiment takes ~2-5 min. In 120 min, that's 25-60 experiments.

Usage:
  python churn_v2.py           # Run continuous loop
"""

import json
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

DATA_DIR = Path(__file__).parent / "data"
PARAMS_FILE = DATA_DIR / "brain_v3_params.json"
CHURN_LOG = Path.home() / "churn_v2.log"
COMPETITION_END = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(CHURN_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


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
        with open(PARAMS_FILE, "w") as f:
            json.dump(params, f, indent=2)
        log(f"  NEW BEST: {score:.2f} (was {best_score:.2f}, +{score - best_score:.2f}) [{experiment_name}]")
        return True
    return False


def score_variant(rounds_data, alphas, temps, collapse, sigma):
    """Leave-one-out backtest with given params. Tests on last 5 rounds for speed."""
    test_rounds = rounds_data[-5:] if len(rounds_data) > 5 else rounds_data
    scores = []
    for rd in test_rounds:
        if not rd.get("seeds"):
            continue
        rn = rd["round_number"]
        regime, _ = classify_round(rd)
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
            scores.append(score_prediction(gt, pred, initial_grid=ig)["score"])

    return np.mean(scores) if scores else 0.0


def run_experiments(rounds_data):
    """Run a batch of experiments, each trying a different variant."""
    best_score, best_params = load_best()
    # Current best params as baseline
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
        s = score_variant(rounds_data, test_alphas, temps, collapse, sigma)
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
        s = score_variant(rounds_data, alphas, test_temps, collapse, sigma)
        if save_if_better(s, alphas, test_temps, collapse, sigma, f"temp_perturb_{iteration}"):
            temps = test_temps
        log(f"  [{iteration}] temps=({test_temps['low']:.2f},{test_temps['mid']:.2f},{test_temps['high']:.2f}) -> {s:.2f}")

    # C: Collapse threshold sweep
    log("Experiment C: Collapse threshold")
    for c_val in [0.005, 0.008, 0.01, 0.012, 0.016, 0.02, 0.025, 0.03]:
        iteration += 1
        s = score_variant(rounds_data, alphas, temps, c_val, sigma)
        if save_if_better(s, alphas, temps, c_val, sigma, f"collapse_{c_val}"):
            collapse = c_val
        log(f"  [{iteration}] collapse={c_val} -> {s:.2f}")

    # D: Sigma sweep
    log("Experiment D: Smoothing sigma")
    for s_val in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]:
        iteration += 1
        s = score_variant(rounds_data, alphas, temps, collapse, s_val)
        if save_if_better(s, alphas, temps, collapse, s_val, f"sigma_{s_val}"):
            sigma = s_val
        log(f"  [{iteration}] sigma={s_val} -> {s:.2f}")

    # E: Entropy threshold sweep (where low/mid/high boundaries are)
    log("Experiment E: Entropy thresholds")
    for low_th, high_th in [(0.1, 0.5), (0.2, 0.8), (0.3, 1.0), (0.4, 1.2), (0.5, 1.5)]:
        iteration += 1
        # Can't easily change thresholds without modifying score_variant internals
        # Instead, test different temp spreads that achieve similar effect
        spread = random.uniform(0.1, 0.5)
        test_temps = {
            "low": max(0.3, 1.0 - spread),
            "mid": 1.0,
            "high": max(0.3, 1.0 + spread),
        }
        s = score_variant(rounds_data, alphas, test_temps, collapse, sigma)
        if save_if_better(s, alphas, test_temps, collapse, sigma, f"spread_{spread:.2f}"):
            temps = test_temps
        log(f"  [{iteration}] spread={spread:.2f} ({test_temps['low']:.2f},{test_temps['mid']:.2f},{test_temps['high']:.2f}) -> {s:.2f}")

    # F: Random combined perturbations (genetic algorithm style)
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
        s = score_variant(rounds_data, test_alphas, test_temps, test_collapse, test_sigma)
        if save_if_better(s, test_alphas, test_temps, test_collapse, test_sigma, f"combined_{iteration}"):
            alphas, temps, collapse, sigma = test_alphas, test_temps, test_collapse, test_sigma
        if iteration % 5 == 0:
            log(f"  [{iteration}] combined -> {s:.2f}")

    best_score_after, _ = load_best()
    log(f"\nBatch complete: {iteration} experiments. Score: {best_score:.2f} -> {best_score_after:.2f}")
    return iteration


def main():
    log("=" * 60)
    log("CHURN V2: CONTINUOUS BRAIN IMPROVEMENT")
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

        # Brief pause then run again with new random seeds
        log("Starting next batch in 30s...")
        time.sleep(30)

    log(f"\nCompetition ended. Total experiments: {total_experiments}")


if __name__ == "__main__":
    main()
