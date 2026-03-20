#!/usr/bin/env python3
"""
Astar Island Simulation Engine — Offline strategy testing with Monte Carlo.

Simulates stochastic observations by sampling from ground truth distributions,
tests different query strategies, and ranks them by score.

Usage:
  python simulate.py --cached-only                    # Run all strategies
  python simulate.py --cached-only --trials 50        # Fewer trials (faster)
  python simulate.py --cached-only --round 4          # Test on specific round
  python simulate.py --cached-only --learn-weights    # Learn query value weights
"""

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    PredictionModel, load_cached_rounds, score_prediction,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES, PROB_FLOOR,
)
from churn import NeighborhoodModelV2
from scipy.ndimage import gaussian_filter

DATA_DIR = Path(__file__).parent / "data"

# Post-processing constants (from PP-001 backtest search)
TEMPERATURE = 1.12
COLLAPSE_THRESH = 0.016
SMOOTH_SIGMA = 0.3


def apply_postprocessing(pred, grid, h, w):
    """Apply temperature scaling, collapse thresholding, and spatial smoothing."""
    # Temperature scaling
    pred = pred ** (1.0 / TEMPERATURE)

    # Collapse thresholding
    for y in range(h):
        for x in range(w):
            if grid[y][x] in STATIC_TERRAIN:
                continue
            probs = pred[y, x]
            mask = probs < COLLAPSE_THRESH
            if mask.any() and not mask.all():
                probs[mask] = 0.0
                probs[:] = np.maximum(probs, PROB_FLOOR)
                pred[y, x] = probs / probs.sum()

    # Spatial smoothing
    smoothed = np.copy(pred)
    for cls in range(NUM_CLASSES):
        smoothed[:, :, cls] = gaussian_filter(pred[:, :, cls], sigma=SMOOTH_SIGMA)
    for y in range(h):
        for x in range(w):
            if grid[y][x] in STATIC_TERRAIN:
                smoothed[y, x] = pred[y, x]
    pred = smoothed

    # Floor and renormalize
    pred = np.maximum(pred, PROB_FLOOR)
    pred = pred / pred.sum(axis=-1, keepdims=True)
    return pred


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ──────────────────────────────────────────────
# Observation Simulator
# ──────────────────────────────────────────────

class ObservationSimulator:
    """Simulates stochastic observations by sampling from ground truth."""

    def __init__(self, round_data, rng=None):
        self.round_data = round_data
        self.h = round_data["map_height"]
        self.w = round_data["map_width"]
        self.rng = rng or np.random.default_rng()
        self.seeds_gt = {}
        for si_str, seed_data in round_data["seeds"].items():
            self.seeds_gt[int(si_str)] = np.array(seed_data["ground_truth"])

    def observe(self, seed_idx, vx, vy, vw=15, vh=15):
        """Simulate one observation viewport. Returns sampled terrain grid."""
        gt = self.seeds_gt.get(seed_idx)
        if gt is None:
            return None
        grid = np.zeros((vh, vw), dtype=int)
        for dy in range(vh):
            for dx in range(vw):
                y, x = vy + dy, vx + dx
                if 0 <= y < self.h and 0 <= x < self.w:
                    probs = gt[y, x]
                    probs = np.maximum(probs, 1e-10)
                    probs = probs / probs.sum()
                    grid[dy, dx] = self.rng.choice(NUM_CLASSES, p=probs)
        return grid


# ──────────────────────────────────────────────
# Query Strategy Execution
# ──────────────────────────────────────────────

def tile_viewports(height, width, vsize=15):
    viewports = []
    for vy in range(0, height, vsize):
        for vx in range(0, width, vsize):
            vh = min(vsize, height - vy)
            vw = min(vsize, width - vx)
            viewports.append((vx, vy, vw, vh))
    return viewports


def compute_surprise_map(obs_counts, obs_total, grid, prior_trans, h, w):
    """Compute per-cell surprise for adaptive targeting."""
    surprise = np.zeros((h, w))
    for y in range(h):
        for x in range(w):
            if obs_total[y, x] == 0:
                continue
            terrain = grid[y][x]
            if terrain in STATIC_TERRAIN:
                continue
            cls = TERRAIN_TO_CLASS.get(int(terrain), 0)
            prior = prior_trans[cls]
            empirical = obs_counts[y, x] / obs_total[y, x]
            diff = np.abs(empirical - prior)
            surprise[y, x] = diff.sum()
            if cls in (1, 2, 3):
                surprise[y, x] *= 3.0
    return surprise


def select_viewports_by_need(need_map, h, w, n_viewports, used=None):
    """Select viewports covering highest-need areas."""
    if used is None:
        used = np.zeros((h, w), dtype=bool)
    viewports = []
    for _ in range(n_viewports):
        best_score = -1
        best_vp = None
        for vy in range(0, max(1, h - 14), 3):
            for vx in range(0, max(1, w - 14), 3):
                region = need_map[vy:vy+15, vx:vx+15]
                region_used = used[vy:vy+15, vx:vx+15]
                score = region[~region_used].sum() if (~region_used).any() else 0
                if score > best_score:
                    best_score = score
                    best_vp = (vx, vy, 15, 15)
        if best_vp and best_score > 0:
            viewports.append(best_vp)
            vx, vy, _, _ = best_vp
            used[vy:vy+15, vx:vx+15] = True
        else:
            break
    return viewports


def build_initial_heat(grid, h, w):
    """Build initial heat map from terrain (settlements/ports = high priority)."""
    heat = np.zeros((h, w))
    for y in range(h):
        for x in range(w):
            cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
            if cls in (1, 2):
                heat[y, x] += 3
            elif cls == 3:
                heat[y, x] += 2
            elif grid[y][x] not in STATIC_TERRAIN:
                has_adj = any(
                    0 <= y+dy < h and 0 <= x+dx < w
                    and TERRAIN_TO_CLASS.get(int(grid[y+dy][x+dx]), 0) in (1, 2)
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0)
                )
                if has_adj:
                    heat[y, x] += 2
    return heat


def execute_strategy(strategy, sim, seed_idx, model, hist_trans, round_trans,
                     v2_model=None):
    """Execute a query strategy and return the final prediction + score.

    strategy: dict with "batches" list, each batch has:
        queries: int (0 = analysis step, >0 = observation step)
        target: "overview" | "heat" | "surprise" | "settlement_only"
        seed: int (which seed to observe)

    If v2_model is provided, uses V2 model for final prediction (ignores old model).
    """
    rd = sim.round_data
    h, w = rd["map_height"], rd["map_width"]
    grid = rd["initial_states"][seed_idx]["grid"]

    obs_counts = np.zeros((h, w, NUM_CLASSES))
    obs_total = np.zeros((h, w))

    # Build initial heat map
    heat = build_initial_heat(grid, h, w)
    current_targets = select_viewports_by_need(heat, h, w, 8)

    # Build a basic prior transition for surprise calculation
    prior_trans = hist_trans["global"] if isinstance(hist_trans, dict) and "global" in hist_trans else hist_trans

    total_queries_used = 0

    for batch in strategy["batches"]:
        n_queries = batch["queries"]
        target = batch["target"]
        obs_seed = batch.get("seed", seed_idx)

        if n_queries == 0 and target == "hindsight":
            # Analysis step: recompute targets based on surprise
            surprise = compute_surprise_map(obs_counts, obs_total, grid,
                                             prior_trans, h, w)
            # Combine surprise with low-sample bonus
            need = surprise.copy()
            low_sample = np.maximum(0, 4 - obs_total)
            need += low_sample * 0.5
            current_targets = select_viewports_by_need(need, h, w, 8)
            continue

        if n_queries == 0:
            continue

        # Select viewports for this batch
        if target == "overview":
            viewports = tile_viewports(h, w, 15)[:n_queries]
        elif target == "heat":
            viewports = current_targets[:n_queries]
            if len(viewports) < n_queries:
                viewports = select_viewports_by_need(heat, h, w, n_queries)
        elif target == "surprise":
            viewports = current_targets[:n_queries]
            if len(viewports) < n_queries:
                viewports = select_viewports_by_need(heat, h, w, n_queries)
        elif target == "settlement_only":
            # Target only settlement/port cells
            settle_heat = np.zeros((h, w))
            for y in range(h):
                for x in range(w):
                    cls = TERRAIN_TO_CLASS.get(int(grid[y][x]), 0)
                    if cls in (1, 2):
                        settle_heat[y, x] += 5
                    elif cls == 3:
                        settle_heat[y, x] += 3
                    elif grid[y][x] not in STATIC_TERRAIN:
                        has_adj = any(
                            0 <= y+dy < h and 0 <= x+dx < w
                            and TERRAIN_TO_CLASS.get(int(grid[y+dy][x+dx]), 0) in (1, 2)
                            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if (dy, dx) != (0, 0)
                        )
                        if has_adj:
                            settle_heat[y, x] += 2
            viewports = select_viewports_by_need(settle_heat, h, w, n_queries)
        else:
            viewports = current_targets[:n_queries]

        # Execute queries
        for vx, vy, vw, vh in viewports[:n_queries]:
            if total_queries_used >= 50:
                break
            sampled = sim.observe(obs_seed, vx, vy, vw, vh)
            if sampled is None:
                continue
            for dy in range(vh):
                for dx in range(vw):
                    ya, xa = vy + dy, vx + dx
                    if 0 <= ya < h and 0 <= xa < w:
                        obs_counts[ya, xa, sampled[dy, dx]] += 1
                        obs_total[ya, xa] += 1
            total_queries_used += 1

    # Build prediction
    if v2_model is not None:
        pred = v2_model.predict_grid_with_obs(
            rd, seed_idx, obs_counts=obs_counts, obs_total=obs_total,
            obs_weight_max=0.70)
    else:
        pred = model.predict_seed(rd, seed_idx, hist_trans, round_trans,
                                   obs_counts=obs_counts, obs_total=obs_total)

    # Apply post-processing (temperature, collapse, smoothing)
    pred = apply_postprocessing(pred, grid, h, w)

    # Score against ground truth
    gt = np.array(rd["seeds"][str(seed_idx)]["ground_truth"])
    ig = rd["initial_states"][seed_idx]["grid"]
    result = score_prediction(gt, pred, initial_grid=ig)

    return result["score"], total_queries_used


# ──────────────────────────────────────────────
# Strategy Definitions
# ──────────────────────────────────────────────

STRATEGIES = {
    "A_blind_stack": {
        "description": "Current: 9 overview + 41 blind stacking (no hindsight)",
        "batches": [
            {"queries": 9, "target": "overview", "seed": 0},
            {"queries": 41, "target": "heat", "seed": 0},
        ],
    },
    "B_adaptive_4x10": {
        "description": "9 overview + 4 batches of ~10 with hindsight between each",
        "batches": [
            {"queries": 9, "target": "overview", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 10, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 10, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 10, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 11, "target": "surprise", "seed": 0},
        ],
    },
    "C_adaptive_8x5": {
        "description": "9 overview + 8 batches of 5 with hindsight between each",
        "batches": [
            {"queries": 9, "target": "overview", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 5, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 5, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 5, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 5, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 5, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 5, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 6, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 5, "target": "surprise", "seed": 0},
        ],
    },
    "D_settlement_focus": {
        "description": "9 overview + 41 stacking only on settlement/port areas",
        "batches": [
            {"queries": 9, "target": "overview", "seed": 0},
            {"queries": 41, "target": "settlement_only", "seed": 0},
        ],
    },
    "E_multi_seed": {
        "description": "9 overview seed 0, 9 overview seed 1, 32 split stacking",
        "batches": [
            {"queries": 9, "target": "overview", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 16, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 16, "target": "surprise", "seed": 0},
            # Seed 1 gets 9 overview queries
            {"queries": 9, "target": "overview", "seed": 1},
        ],
    },
    "F_greedy_2x20": {
        "description": "9 overview + 2 large adaptive batches with hindsight",
        "batches": [
            {"queries": 9, "target": "overview", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 20, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 21, "target": "surprise", "seed": 0},
        ],
    },
    "G_rapid_adapt_5x8": {
        "description": "9 overview + 5 batches of 8 with hindsight (matches current adaptive code)",
        "batches": [
            {"queries": 9, "target": "overview", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 8, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 8, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 8, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 8, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 9, "target": "surprise", "seed": 0},
        ],
    },
    "H_no_overview": {
        "description": "Skip overview entirely, 50 adaptive queries on hot zones",
        "batches": [
            {"queries": 10, "target": "heat", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 10, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 10, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 10, "target": "surprise", "seed": 0},
            {"queries": 0, "target": "hindsight"},
            {"queries": 10, "target": "surprise", "seed": 0},
        ],
    },
}


# ──────────────────────────────────────────────
# Monte Carlo Runner
# ──────────────────────────────────────────────

def monte_carlo_strategy(strategy, round_data, model, hist_trans, round_trans,
                          n_trials=50, seeds_to_test=None, v2_model=None):
    """Run a strategy n_trials times on a round, return score statistics.

    Tests on seed 0 by default (our primary observed seed).
    Cross-seed transfer applied to all seeds for final scoring.
    If v2_model provided, uses V2 NeighborhoodModel for predictions.
    """
    if seeds_to_test is None:
        seeds_to_test = [0]

    all_scores = []

    for trial in range(n_trials):
        rng = np.random.default_rng(seed=trial * 1000 + 42)
        sim = ObservationSimulator(round_data, rng=rng)

        trial_scores = []
        for seed_idx in seeds_to_test:
            if str(seed_idx) not in round_data["seeds"]:
                continue
            score, queries_used = execute_strategy(
                strategy, sim, seed_idx, model, hist_trans, round_trans,
                v2_model=v2_model
            )
            trial_scores.append(score)

        # For unobserved seeds, use model-only prediction + post-processing
        for seed_idx in range(round_data.get("seeds_count", 5)):
            if seed_idx in seeds_to_test:
                continue
            if str(seed_idx) not in round_data["seeds"]:
                continue
            h, w = round_data["map_height"], round_data["map_width"]
            grid = round_data["initial_states"][seed_idx]["grid"]
            if v2_model is not None:
                pred = v2_model.predict_grid(round_data, seed_idx)
            else:
                pred = model.predict_seed(round_data, seed_idx, hist_trans, round_trans)
            pred = apply_postprocessing(pred, grid, h, w)
            gt = np.array(round_data["seeds"][str(seed_idx)]["ground_truth"])
            ig = round_data["initial_states"][seed_idx]["grid"]
            result = score_prediction(gt, pred, initial_grid=ig)
            trial_scores.append(result["score"])

        if trial_scores:
            all_scores.append(np.mean(trial_scores))

    return {
        "mean": round(float(np.mean(all_scores)), 2),
        "std": round(float(np.std(all_scores)), 2),
        "min": round(float(np.min(all_scores)), 2),
        "max": round(float(np.max(all_scores)), 2),
        "median": round(float(np.median(all_scores)), 2),
        "n_trials": n_trials,
    }


# ──────────────────────────────────────────────
# Weight Learning
# ──────────────────────────────────────────────

def learn_query_weights(rounds_data, model, n_trials=30):
    """Learn per-cell-type query value weights through simulation.

    For each terrain type, measures: how much does observing this cell type
    improve the prediction, across many rounds and Monte Carlo trials?

    Returns weights dict: terrain_name -> average info value per query.
    """
    log("Learning query value weights...")

    terrain_value = {name: [] for name in CLASS_NAMES}

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        hist_trans = model.build_transitions(rounds_data, exclude_round=rn)

        for trial in range(n_trials):
            rng = np.random.default_rng(seed=trial * 100 + rn)
            sim = ObservationSimulator(rd, rng=rng)
            h, w = rd["map_height"], rd["map_width"]

            for si in range(min(2, rd.get("seeds_count", 5))):
                si_str = str(si)
                if si_str not in rd["seeds"]:
                    continue

                gt = np.array(rd["seeds"][si_str]["ground_truth"])
                ig = rd["initial_states"][si]["grid"]

                # Baseline: no-observation prediction
                pred_base = model.predict_seed(rd, si, hist_trans, hist_trans)
                score_base = score_prediction(gt, pred_base, initial_grid=ig)

                # For each terrain type, simulate observing ONLY those cells
                for cls_idx, cls_name in enumerate(CLASS_NAMES):
                    if cls_name == "Mountain":
                        continue

                    obs_counts = np.zeros((h, w, NUM_CLASSES))
                    obs_total = np.zeros((h, w))
                    queries_used = 0

                    # Find cells of this terrain type and observe a sample
                    cells = []
                    for y in range(h):
                        for x in range(w):
                            if TERRAIN_TO_CLASS.get(int(ig[y][x]), 0) == cls_idx:
                                cells.append((y, x))

                    # Observe up to 10 random cells of this type (5 samples each)
                    if cells:
                        sample_cells = rng.choice(len(cells), size=min(10, len(cells)),
                                                   replace=False)
                        for ci in sample_cells:
                            cy, cx = cells[ci]
                            for _ in range(5):
                                sampled = sim.observe(si, cx, cy, 1, 1)
                                if sampled is not None:
                                    obs_counts[cy, cx, sampled[0, 0]] += 1
                                    obs_total[cy, cx] += 1
                                    queries_used += 1

                    if queries_used == 0:
                        continue

                    pred_obs = model.predict_seed(rd, si, hist_trans, hist_trans,
                                                   obs_counts=obs_counts,
                                                   obs_total=obs_total)
                    score_obs = score_prediction(gt, pred_obs, initial_grid=ig)
                    value = (score_obs["score"] - score_base["score"]) / max(1, queries_used)
                    terrain_value[cls_name].append(value)

    weights = {}
    for cls_name in CLASS_NAMES:
        vals = terrain_value[cls_name]
        if vals:
            weights[cls_name] = {
                "avg_value_per_query": round(float(np.mean(vals)), 4),
                "std": round(float(np.std(vals)), 4),
                "n_samples": len(vals),
                "verdict": "HIGH" if np.mean(vals) > 0.05 else
                          "MEDIUM" if np.mean(vals) > 0 else "LOW/NEGATIVE",
            }
        else:
            weights[cls_name] = {"avg_value_per_query": 0, "verdict": "SKIP"}

    return weights


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Astar Island Simulation Engine")
    parser.add_argument("--cached-only", action="store_true")
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--learn-weights", action="store_true")
    parser.add_argument("--strategy", type=str, default=None,
                        help="Test specific strategy only (e.g., B_adaptive_4x10)")
    args = parser.parse_args()

    all_rounds = load_cached_rounds()
    if not all_rounds:
        log("No cached data. Run backtest.py --cache first.")
        return

    if args.round:
        rounds_data = [rd for rd in all_rounds if rd["round_number"] == args.round]
    else:
        rounds_data = all_rounds

    # Old model kept for strategy logic (heat maps, viewport selection)
    model = PredictionModel({
        "near_dist_1": 0.6, "near_dist_3": 0.4, "near_dist_5": 0.2,
        "forest_bonus_per_adj": 0.0, "forest_bonus_cap": 0.0,
    })

    if args.learn_weights:
        weights = learn_query_weights(rounds_data, model, n_trials=args.trials)
        log("\nQuery Value Weights:")
        for cls_name in CLASS_NAMES:
            w = weights[cls_name]
            log(f"  {cls_name}: {w['avg_value_per_query']:+.4f}/query ({w['verdict']})")

        weights_path = DATA_DIR / "replays" / "learned_weights.json"
        weights_path.parent.mkdir(parents=True, exist_ok=True)
        weights_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "weights": weights,
        }, indent=2))
        log(f"Saved: {weights_path}")
        return

    # Run strategy tournament
    strategies_to_test = STRATEGIES
    if args.strategy:
        if args.strategy in STRATEGIES:
            strategies_to_test = {args.strategy: STRATEGIES[args.strategy]}
        else:
            log(f"Unknown strategy: {args.strategy}. Available: {list(STRATEGIES.keys())}")
            return

    log(f"Testing {len(strategies_to_test)} strategies across {len(rounds_data)} rounds "
        f"({args.trials} Monte Carlo trials each)")

    all_results = {}

    for strat_name, strategy in strategies_to_test.items():
        log(f"\n{'='*50}")
        log(f"  Strategy: {strat_name}")
        log(f"  {strategy['description']}")
        log(f"{'='*50}")

        strat_results = []

        for rd in rounds_data:
            rn = rd["round_number"]
            if not rd.get("seeds"):
                continue

            hist_trans = model.build_transitions(all_rounds, exclude_round=rn)

            # Build V2 model for this round (leave-one-out, uses ALL rounds)
            v2 = NeighborhoodModelV2()
            for other_rd in all_rounds:
                if other_rd["round_number"] != rn and other_rd.get("seeds"):
                    v2.add_training_data(other_rd)
            v2.finalize()

            mc = monte_carlo_strategy(
                strategy, rd, model, hist_trans, hist_trans,
                n_trials=args.trials, seeds_to_test=[0], v2_model=v2
            )
            strat_results.append({
                "round": rn,
                "weight": rd.get("round_weight", 1.0),
                **mc,
            })
            log(f"  R{rn}: {mc['mean']:.1f} +/- {mc['std']:.1f} "
                f"(range {mc['min']:.1f}-{mc['max']:.1f})")

        avg_score = np.mean([r["mean"] for r in strat_results])
        best_round = max(strat_results, key=lambda r: r["mean"])

        all_results[strat_name] = {
            "description": strategy["description"],
            "avg_score": round(float(avg_score), 2),
            "best_round_score": round(float(best_round["mean"]), 2),
            "best_round": best_round["round"],
            "per_round": strat_results,
        }
        log(f"\n  Average: {avg_score:.1f}, Best: {best_round['mean']:.1f} (R{best_round['round']})")

    # Rank strategies
    ranked = sorted(all_results.items(), key=lambda x: -x[1]["avg_score"])

    log(f"\n{'='*60}")
    log(f"  STRATEGY RANKING")
    log(f"{'='*60}")
    log(f"  {'Rank':<5} {'Strategy':<25} {'Avg':>6} {'Best':>6} {'Description'}")
    log(f"  {'-'*80}")
    for i, (name, result) in enumerate(ranked):
        log(f"  {i+1:<5} {name:<25} {result['avg_score']:>6.1f} "
            f"{result['best_round_score']:>6.1f} {result['description'][:40]}")

    # Save results
    output_path = DATA_DIR / "replays" / "strategies_ranked.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trials_per_round": args.trials,
        "rounds_tested": [rd["round_number"] for rd in rounds_data],
        "ranking": [{"rank": i+1, "name": name, **result}
                    for i, (name, result) in enumerate(ranked)],
    }, indent=2))
    log(f"\nSaved: {output_path}")

    # Save best strategy config
    best_name = ranked[0][0]
    best_path = DATA_DIR / "replays" / "best_strategy.json"
    best_path.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy_name": best_name,
        "strategy": STRATEGIES[best_name],
        "avg_score": ranked[0][1]["avg_score"],
        "delta_vs_baseline": round(ranked[0][1]["avg_score"] - all_results.get("A_blind_stack", {}).get("avg_score", 0), 2),
    }, indent=2))
    log(f"Best strategy: {best_name} (saved to {best_path})")


if __name__ == "__main__":
    main()
