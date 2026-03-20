#!/usr/bin/env python3
"""
Brain V3: Optimized prediction model for Astar Island.

Improvements over V2:
1. Per-terrain Dirichlet alpha (fitted from backtest data)
2. Entropy-aware temperature scaling (different T for uncertain vs confident cells)
3. Regime-specific transition tables
4. Auto-fitting: all params optimized from ground truth data

Usage:
  python brain_v3.py                     # Backtest comparison vs V2
  python brain_v3.py --fit               # Fit optimal alphas and temperatures
  python brain_v3.py --fit --deploy      # Fit and save params for overnight runner
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from scipy.optimize import minimize
from scipy.ndimage import gaussian_filter

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR, CLASS_NAMES,
)
from regime_model import classify_round, extract_features, key_full, key_reduced, key_minimal, RegimeModel

DATA_DIR = Path(__file__).parent / "data"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


class BrainV3:
    """Optimized prediction model with per-terrain alpha and entropy-aware temperature."""

    LEVELS = ["full", "reduced", "minimal"]
    KEY_FNS = {"full": key_full, "reduced": key_reduced, "minimal": key_minimal}

    def __init__(self, alphas=None, temps=None, collapse=0.016, sigma=0.3,
                 min_full=5, min_reduced=10, use_regime=True):
        # Per-terrain Dirichlet alpha: how confident are we in the model prior?
        # Higher alpha = trust model more, lower = trust observations more
        self.alphas = alphas or {
            0: 8.0,   # Empty: moderate confidence
            1: 4.0,   # Settlement: low confidence (most uncertain)
            2: 3.0,   # Port: very low confidence (rare)
            3: 3.0,   # Ruin: very low confidence (rare)
            4: 10.0,  # Forest: higher confidence (mostly stable)
            5: 50.0,  # Mountain: very high confidence (static)
        }
        # Entropy-aware temperature: different T for high vs low entropy cells
        self.temps = temps or {
            "low": 0.9,    # Confident cells: sharpen prediction
            "mid": 1.1,    # Medium cells: slight softening
            "high": 1.3,   # Uncertain cells: widen prediction
        }
        self.collapse = collapse
        self.sigma = sigma
        self.min_full = min_full
        self.min_reduced = min_reduced
        self.use_regime = use_regime

        # Regime-specific tables
        self.regime_tables = {}  # regime -> level -> key -> [sum_dist, count]
        self.regime_global = {}
        self.overall_tables = {lvl: {} for lvl in self.LEVELS}
        self.overall_global = {}
        self.regime_dists = {}
        self.regime_global_dists = {}
        self.overall_dists = {lvl: {} for lvl in self.LEVELS}
        self.overall_global_dists = {}
        self.total_cells = 0
        self.training_rounds = []

    def add_training_data(self, round_data):
        """Add training data, auto-classifying into regime."""
        rn = round_data["round_number"]
        regime, _ = classify_round(round_data)
        h, w = round_data["map_height"], round_data["map_width"]

        if regime not in self.regime_tables:
            self.regime_tables[regime] = {lvl: {} for lvl in self.LEVELS}
            self.regime_global[regime] = {}

        for si_str, seed_data in round_data.get("seeds", {}).items():
            si = int(si_str)
            ig = round_data["initial_states"][si]["grid"]
            gt = np.array(seed_data["ground_truth"])

            for y in range(h):
                for x in range(w):
                    if int(ig[y][x]) in STATIC_TERRAIN:
                        continue
                    my_cls, counts, dist_b, sr3 = extract_features(ig, y, x, h, w)
                    gt_dist = gt[y, x]

                    # Add to regime-specific tables
                    for lvl, kfn in self.KEY_FNS.items():
                        key = kfn(my_cls, counts, dist_b, sr3)
                        # Regime
                        if key not in self.regime_tables[regime][lvl]:
                            self.regime_tables[regime][lvl][key] = [np.zeros(NUM_CLASSES), 0]
                        self.regime_tables[regime][lvl][key][0] += gt_dist
                        self.regime_tables[regime][lvl][key][1] += 1
                        # Overall
                        if key not in self.overall_tables[lvl]:
                            self.overall_tables[lvl][key] = [np.zeros(NUM_CLASSES), 0]
                        self.overall_tables[lvl][key][0] += gt_dist
                        self.overall_tables[lvl][key][1] += 1

                    # Regime global
                    if my_cls not in self.regime_global[regime]:
                        self.regime_global[regime][my_cls] = [np.zeros(NUM_CLASSES), 0]
                    self.regime_global[regime][my_cls][0] += gt_dist
                    self.regime_global[regime][my_cls][1] += 1
                    # Overall global
                    if my_cls not in self.overall_global:
                        self.overall_global[my_cls] = [np.zeros(NUM_CLASSES), 0]
                    self.overall_global[my_cls][0] += gt_dist
                    self.overall_global[my_cls][1] += 1

                    self.total_cells += 1

        self.training_rounds.append(rn)

    def finalize(self):
        """Normalize all tables."""
        def norm_table(table):
            d = {}
            for key, (s, c) in table.items():
                if c > 0:
                    dist = s / c
                    dist = np.maximum(dist, PROB_FLOOR)
                    dist /= dist.sum()
                    d[key] = dist
            return d

        for regime in self.regime_tables:
            self.regime_dists[regime] = {}
            for lvl in self.LEVELS:
                self.regime_dists[regime][lvl] = norm_table(self.regime_tables[regime][lvl])
            self.regime_global_dists[regime] = {}
            for cls, (s, c) in self.regime_global[regime].items():
                if c > 0:
                    d = s / c
                    d = np.maximum(d, PROB_FLOOR)
                    d /= d.sum()
                    self.regime_global_dists[regime][cls] = d

        for lvl in self.LEVELS:
            self.overall_dists[lvl] = norm_table(self.overall_tables[lvl])
        for cls, (s, c) in self.overall_global.items():
            if c > 0:
                d = s / c
                d = np.maximum(d, PROB_FLOOR)
                d /= d.sum()
                self.overall_global_dists[cls] = d

    def predict_cell(self, grid, y, x, h, w, regime="stable"):
        """Predict one cell using regime-specific hierarchical lookup."""
        terrain = grid[y][x]
        if terrain in STATIC_TERRAIN:
            cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
            dist = np.full(NUM_CLASSES, PROB_FLOOR)
            dist[cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR
            return dist

        my_cls, counts, dist_b, sr3 = extract_features(grid, y, x, h, w)

        # Try regime-specific first (if enabled and available)
        if self.use_regime and regime in self.regime_dists:
            rdist = self.regime_dists[regime]
            k = key_full(my_cls, counts, dist_b, sr3)
            if k in rdist["full"]:
                c = self.regime_tables[regime]["full"][k][1]
                if c >= self.min_full:
                    return rdist["full"][k].copy()
            k = key_reduced(my_cls, counts, dist_b, sr3)
            if k in rdist["reduced"]:
                c = self.regime_tables[regime]["reduced"][k][1]
                if c >= self.min_reduced:
                    return rdist["reduced"][k].copy()
            k = key_minimal(my_cls, counts, dist_b, sr3)
            if k in rdist["minimal"]:
                return rdist["minimal"][k].copy()
            if regime in self.regime_global_dists and my_cls in self.regime_global_dists[regime]:
                return self.regime_global_dists[regime][my_cls].copy()

        # Fall back to overall
        k = key_full(my_cls, counts, dist_b, sr3)
        if k in self.overall_dists["full"]:
            c = self.overall_tables["full"][k][1]
            if c >= self.min_full:
                return self.overall_dists["full"][k].copy()
        k = key_reduced(my_cls, counts, dist_b, sr3)
        if k in self.overall_dists["reduced"]:
            c = self.overall_tables["reduced"][k][1]
            if c >= self.min_reduced:
                return self.overall_dists["reduced"][k].copy()
        k = key_minimal(my_cls, counts, dist_b, sr3)
        if k in self.overall_dists["minimal"]:
            return self.overall_dists["minimal"][k].copy()
        if my_cls in self.overall_global_dists:
            return self.overall_global_dists[my_cls].copy()

        return np.full(NUM_CLASSES, 1.0 / NUM_CLASSES)

    def predict_grid(self, detail, seed_idx, regime="stable"):
        """Predict full grid."""
        h, w = detail["map_height"], detail["map_width"]
        grid = detail["initial_states"][seed_idx]["grid"]
        pred = np.zeros((h, w, NUM_CLASSES))
        for y in range(h):
            for x in range(w):
                pred[y, x] = self.predict_cell(grid, y, x, h, w, regime)
        return pred

    def predict_with_obs(self, detail, seed_idx, regime="stable",
                         obs_counts=None, obs_total=None):
        """Predict with per-terrain Dirichlet alpha and entropy-aware temperature."""
        h, w = detail["map_height"], detail["map_width"]
        grid = detail["initial_states"][seed_idx]["grid"]
        pred = self.predict_grid(detail, seed_idx, regime)

        # Per-terrain Dirichlet observation blending
        if obs_counts is not None and obs_total is not None:
            for y in range(h):
                for x in range(w):
                    if obs_total[y, x] == 0:
                        continue
                    init_cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    alpha_val = self.alphas.get(init_cls, 8.0)
                    alpha = alpha_val * pred[y, x]
                    alpha = np.maximum(alpha, PROB_FLOOR)
                    posterior = (alpha + obs_counts[y, x]) / (alpha.sum() + obs_total[y, x])
                    pred[y, x] = posterior

        # Entropy-aware temperature scaling
        for y in range(h):
            for x in range(w):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                # Compute predicted entropy
                p = pred[y, x]
                p_safe = np.maximum(p, 1e-10)
                ent = -np.sum(p_safe * np.log(p_safe))
                # Choose temperature based on entropy
                if ent < 0.3:
                    t = self.temps["low"]
                elif ent < 1.0:
                    t = self.temps["mid"]
                else:
                    t = self.temps["high"]
                # Apply temperature
                pred[y, x] = pred[y, x] ** (1.0 / t)

        # Collapse thresholding
        for y in range(h):
            for x in range(w):
                if grid[y][x] in STATIC_TERRAIN:
                    continue
                probs = pred[y, x]
                mask = probs < self.collapse
                if mask.any() and not mask.all():
                    probs[mask] = PROB_FLOOR
                    pred[y, x] = probs / probs.sum()

        # Spatial smoothing
        if self.sigma > 0:
            smoothed = np.copy(pred)
            for cls in range(NUM_CLASSES):
                smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=self.sigma)
            for y in range(h):
                for x in range(w):
                    if grid[y][x] in STATIC_TERRAIN:
                        smoothed[y, x] = pred[y, x]
            pred = smoothed

        # Floor and renormalize
        pred = np.maximum(pred, PROB_FLOOR)
        pred = pred / pred.sum(axis=-1, keepdims=True)
        return pred


def fit_alphas(rounds_data):
    """Fit optimal per-terrain Dirichlet alpha values using backtest data."""
    log("Fitting per-terrain alpha values...")

    def objective(params):
        """Negative average score (we minimize, so negate)."""
        alphas = {i: max(0.5, params[i]) for i in range(NUM_CLASSES)}
        scores = []
        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue
            regime, _ = classify_round(rd)
            model = BrainV3(alphas=alphas, use_regime=True)
            for other in rounds_data:
                if other["round_number"] != rn:
                    model.add_training_data(other)
            model.finalize()

            for si_str, seed_data in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(seed_data["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = model.predict_with_obs(rd, si, regime=regime)
                result = score_prediction(gt, pred, initial_grid=ig)
                scores.append(result["score"])
        return -np.mean(scores)

    # Start from reasonable defaults
    x0 = [8.0, 4.0, 3.0, 3.0, 10.0, 50.0]
    log(f"  Initial alphas: {x0}")
    log(f"  Initial score: {-objective(x0):.2f}")

    result = minimize(objective, x0, method="Nelder-Mead",
                      options={"maxiter": 200, "xatol": 0.5, "fatol": 0.1})

    best_alphas = {i: max(0.5, result.x[i]) for i in range(NUM_CLASSES)}
    best_score = -result.fun
    log(f"  Optimized alphas: {[round(best_alphas[i], 1) for i in range(6)]}")
    log(f"  Optimized score: {best_score:.2f}")
    log(f"  ({CLASS_NAMES[0]}={best_alphas[0]:.1f}, {CLASS_NAMES[1]}={best_alphas[1]:.1f}, "
        f"{CLASS_NAMES[4]}={best_alphas[4]:.1f})")
    return best_alphas, best_score


def fit_temps(rounds_data, alphas):
    """Fit entropy-aware temperature values."""
    log("Fitting entropy-aware temperatures...")

    def objective(params):
        temps = {"low": max(0.5, params[0]), "mid": max(0.5, params[1]), "high": max(0.5, params[2])}
        scores = []
        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue
            regime, _ = classify_round(rd)
            model = BrainV3(alphas=alphas, temps=temps, use_regime=True)
            for other in rounds_data:
                if other["round_number"] != rn:
                    model.add_training_data(other)
            model.finalize()

            for si_str, seed_data in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(seed_data["ground_truth"])
                ig = rd["initial_states"][si]["grid"]
                pred = model.predict_with_obs(rd, si, regime=regime)
                result = score_prediction(gt, pred, initial_grid=ig)
                scores.append(result["score"])
        return -np.mean(scores)

    x0 = [0.9, 1.1, 1.3]
    log(f"  Initial temps: low={x0[0]}, mid={x0[1]}, high={x0[2]}")
    log(f"  Initial score: {-objective(x0):.2f}")

    result = minimize(objective, x0, method="Nelder-Mead",
                      options={"maxiter": 100, "xatol": 0.05, "fatol": 0.1})

    best_temps = {
        "low": max(0.5, result.x[0]),
        "mid": max(0.5, result.x[1]),
        "high": max(0.5, result.x[2]),
    }
    best_score = -result.fun
    log(f"  Optimized temps: low={best_temps['low']:.2f}, mid={best_temps['mid']:.2f}, high={best_temps['high']:.2f}")
    log(f"  Optimized score: {best_score:.2f}")
    return best_temps, best_score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit", action="store_true", help="Fit optimal params")
    parser.add_argument("--deploy", action="store_true", help="Save fitted params")
    args = parser.parse_args()

    rounds_data = load_cached_rounds()
    log(f"Loaded {len(rounds_data)} rounds")

    if args.fit:
        # Step 1: Fit alphas
        best_alphas, alpha_score = fit_alphas(rounds_data)

        # Step 2: Fit temperatures with best alphas
        best_temps, temp_score = fit_temps(rounds_data, best_alphas)

        # Step 3: Compare vs V2 baseline
        log("\n=== COMPARISON: Brain V3 vs V2 ===")
        from churn import NeighborhoodModelV2

        v2_scores = []
        v3_scores = []

        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue
            regime, _ = classify_round(rd)

            # V2
            v2 = NeighborhoodModelV2()
            for other in rounds_data:
                if other["round_number"] != rn:
                    v2.add_training_data(other)
            v2.finalize()

            # V3
            v3 = BrainV3(alphas=best_alphas, temps=best_temps, use_regime=True)
            for other in rounds_data:
                if other["round_number"] != rn:
                    v3.add_training_data(other)
            v3.finalize()

            v2_round = []
            v3_round = []
            for si_str, seed_data in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(seed_data["ground_truth"])
                ig = rd["initial_states"][si]["grid"]

                # V2 with old params
                p2 = v2.predict_grid(rd, si)
                p2 = p2 ** (1.0 / 1.12)
                p2 = np.maximum(p2, PROB_FLOOR)
                p2 = p2 / p2.sum(axis=-1, keepdims=True)
                r2 = score_prediction(gt, p2, initial_grid=ig)
                v2_round.append(r2["score"])

                # V3 with fitted params
                p3 = v3.predict_with_obs(rd, si, regime=regime)
                r3 = score_prediction(gt, p3, initial_grid=ig)
                v3_round.append(r3["score"])

            v2_avg = np.mean(v2_round)
            v3_avg = np.mean(v3_round)
            v2_scores.append(v2_avg)
            v3_scores.append(v3_avg)
            delta = v3_avg - v2_avg
            sym = "+" if delta >= 0 else ""
            log(f"R{rn} [{regime:>6}]: V2={v2_avg:.1f}  V3={v3_avg:.1f}  delta={sym}{delta:.1f}")

        v2_overall = np.mean(v2_scores)
        v3_overall = np.mean(v3_scores)
        log(f"\nV2 avg: {v2_overall:.2f}  V3 avg: {v3_overall:.2f}  delta: {v3_overall - v2_overall:+.2f}")

        if args.deploy:
            params = {
                "alphas": {str(k): round(float(v), 2) for k, v in best_alphas.items()},
                "temps": {k: round(float(v), 3) for k, v in best_temps.items()},
                "collapse": 0.016,
                "sigma": 0.3,
                "v2_baseline": round(float(v2_overall), 2),
                "v3_score": round(float(v3_overall), 2),
                "delta": round(float(v3_overall - v2_overall), 2),
                "fitted_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(DATA_DIR / "brain_v3_params.json", "w") as f:
                json.dump(params, f, indent=2)
            log(f"\nDeployed to data/brain_v3_params.json")

    else:
        # Quick comparison with default params
        log("Quick comparison: V3 (defaults) vs V2...")
        from churn import NeighborhoodModelV2

        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue
            regime, _ = classify_round(rd)

            v2 = NeighborhoodModelV2()
            v3 = BrainV3(use_regime=True)
            for other in rounds_data:
                if other["round_number"] != rn:
                    v2.add_training_data(other)
                    v3.add_training_data(other)
            v2.finalize()
            v3.finalize()

            v2_s, v3_s = [], []
            for si_str, sd in rd["seeds"].items():
                si = int(si_str)
                gt = np.array(sd["ground_truth"])
                ig = rd["initial_states"][si]["grid"]

                p2 = v2.predict_grid(rd, si)
                p2 = p2 ** (1.0 / 1.12)
                p2 = np.maximum(p2, PROB_FLOOR)
                p2 /= p2.sum(axis=-1, keepdims=True)

                p3 = v3.predict_with_obs(rd, si, regime=regime)

                v2_s.append(score_prediction(gt, p2, initial_grid=ig)["score"])
                v3_s.append(score_prediction(gt, p3, initial_grid=ig)["score"])

            d = np.mean(v3_s) - np.mean(v2_s)
            log(f"R{rn} [{regime:>6}]: V2={np.mean(v2_s):.1f}  V3={np.mean(v3_s):.1f}  delta={d:+.1f}")


if __name__ == "__main__":
    main()
