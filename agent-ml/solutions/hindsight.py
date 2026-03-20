#!/usr/bin/env python3
"""
Astar Island Hindsight Analyzer — Post-round query analysis.

For each completed round where we have observation data, computes:
A. Per-query information gain (how much did each query reduce prediction error?)
B. Wasted queries (queries on cells where model was already correct)
C. Missed opportunities (high-error cells we never queried)
D. Optimal query allocation (where SHOULD we have queried, knowing ground truth?)
E. Concrete rules for future rounds

Saves replays and analysis as JSON for the dashboard.

Usage:
  python hindsight.py --token TOKEN              # Analyze all rounds with obs data
  python hindsight.py --cached-only              # Use cached ground truth only
  python hindsight.py --cached-only --round 6    # Analyze specific round
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

import numpy as np

# Import from backtest.py
import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    PredictionModel, load_cached_rounds, score_prediction,
    load_real_observations, get_session, cache_round,
    kl_divergence, entropy,
    TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, CLASS_NAMES, PROB_FLOOR,
    BASE
)

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def compute_per_cell_error(ground_truth, prediction, initial_grid):
    """Compute per-cell weighted KL error (same as scoring, but per cell)."""
    gt = np.asarray(ground_truth, dtype=np.float64)
    pred = np.asarray(prediction, dtype=np.float64)
    h, w, _ = gt.shape
    errors = np.zeros((h, w))
    weights = np.zeros((h, w))

    for y in range(h):
        for x in range(w):
            ent = entropy(gt[y, x])
            if ent < 1e-8:
                continue
            kl = kl_divergence(gt[y, x], pred[y, x])
            errors[y, x] = kl
            weights[y, x] = ent
    return errors, weights


def build_prediction_without_obs(model, round_data, seed_idx, hist_trans, round_trans):
    """Build prediction for a seed WITHOUT any observations (model-only baseline)."""
    return model.predict_seed(round_data, seed_idx, hist_trans, round_trans)


def build_prediction_with_obs(model, round_data, seed_idx, hist_trans, round_trans,
                               obs_counts, obs_total):
    """Build prediction WITH observations."""
    return model.predict_seed(round_data, seed_idx, hist_trans, round_trans,
                               obs_counts=obs_counts, obs_total=obs_total)


def analyze_query_value(round_data, seed_idx, obs_counts, obs_total,
                        ground_truth, model, hist_trans, round_trans):
    """Analyze the value of our queries for one seed.

    Compares:
    - Prediction WITHOUT observations (baseline)
    - Prediction WITH observations (what we submitted)
    - Ground truth (what we were trying to predict)
    """
    h, w = round_data["map_height"], round_data["map_width"]
    gt = np.array(ground_truth)
    ig = round_data["initial_states"][seed_idx]["grid"]

    # Baseline: model-only prediction (no observations)
    pred_no_obs = model.predict_seed(round_data, seed_idx, hist_trans, round_trans)
    score_no_obs = score_prediction(gt, pred_no_obs, initial_grid=ig)

    # With observations
    pred_with_obs = model.predict_seed(round_data, seed_idx, hist_trans, round_trans,
                                        obs_counts=obs_counts, obs_total=obs_total)
    score_with_obs = score_prediction(gt, pred_with_obs, initial_grid=ig)

    # Per-cell errors for both
    errors_no_obs, weights = compute_per_cell_error(gt, pred_no_obs, ig)
    errors_with_obs, _ = compute_per_cell_error(gt, pred_with_obs, ig)

    # Information gain per cell: reduction in weighted KL
    info_gain = np.zeros((h, w))
    has_obs = obs_total > 0
    for y in range(h):
        for x in range(w):
            if has_obs[y, x] and weights[y, x] > 0:
                info_gain[y, x] = (errors_no_obs[y, x] - errors_with_obs[y, x]) * weights[y, x]

    # Identify wasted queries: cells where observation didn't help (or hurt)
    wasted = []
    helpful = []
    for y in range(h):
        for x in range(w):
            if not has_obs[y, x]:
                continue
            gain = info_gain[y, x]
            n_samples = int(obs_total[y, x])
            cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
            cell_info = {
                "y": y, "x": x, "terrain": CLASS_NAMES[cls],
                "samples": n_samples, "info_gain": round(float(gain), 4),
                "error_before": round(float(errors_no_obs[y, x]), 4),
                "error_after": round(float(errors_with_obs[y, x]), 4),
            }
            if gain <= 0:
                wasted.append(cell_info)
            else:
                helpful.append(cell_info)

    # Sort by impact
    helpful.sort(key=lambda c: -c["info_gain"])
    wasted.sort(key=lambda c: c["info_gain"])

    # Missed opportunities: high-error cells we never queried
    missed = []
    for y in range(h):
        for x in range(w):
            if has_obs[y, x] or weights[y, x] < 0.01:
                continue
            if errors_no_obs[y, x] > 0.3:
                cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                missed.append({
                    "y": y, "x": x, "terrain": CLASS_NAMES[cls],
                    "error": round(float(errors_no_obs[y, x]), 4),
                    "weight": round(float(weights[y, x]), 4),
                    "weighted_error": round(float(errors_no_obs[y, x] * weights[y, x]), 4),
                })
    missed.sort(key=lambda c: -c["weighted_error"])

    # Optimal allocation: which cells SHOULD we have queried?
    # Rank all non-static cells by weighted error
    all_cells_by_error = []
    for y in range(h):
        for x in range(w):
            if weights[y, x] < 0.01:
                continue
            cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
            all_cells_by_error.append({
                "y": y, "x": x, "terrain": CLASS_NAMES[cls],
                "weighted_error": round(float(errors_no_obs[y, x] * weights[y, x]), 4),
                "was_queried": bool(has_obs[y, x]),
            })
    all_cells_by_error.sort(key=lambda c: -c["weighted_error"])

    # Compute overlap: what % of our queries hit the top-N highest-error cells
    top_n = min(200, len(all_cells_by_error))
    top_cells = set((c["y"], c["x"]) for c in all_cells_by_error[:top_n])
    queried_cells = set((y, x) for y in range(h) for x in range(w) if has_obs[y, x])
    overlap = len(top_cells & queried_cells)
    overlap_pct = overlap / max(1, len(queried_cells)) * 100

    # Per-terrain-class summary
    terrain_summary = {}
    for cls_idx, cls_name in enumerate(CLASS_NAMES):
        cls_queried = 0
        cls_total = 0
        cls_gain = 0.0
        cls_error_before = 0.0
        cls_error_after = 0.0
        cls_weight = 0.0
        for y in range(h):
            for x in range(w):
                if TERRAIN_TO_CLASS.get(int(ig[y][x]), 0) != cls_idx:
                    continue
                if weights[y, x] < 0.01:
                    continue
                cls_total += 1
                cls_weight += weights[y, x]
                cls_error_before += errors_no_obs[y, x] * weights[y, x]
                cls_error_after += errors_with_obs[y, x] * weights[y, x]
                if has_obs[y, x]:
                    cls_queried += 1
                    cls_gain += info_gain[y, x]
        if cls_total > 0:
            terrain_summary[cls_name] = {
                "cells": cls_total,
                "queried": cls_queried,
                "query_pct": round(cls_queried / cls_total * 100, 1),
                "total_info_gain": round(float(cls_gain), 4),
                "avg_error_before": round(float(cls_error_before / cls_weight), 4) if cls_weight > 0 else 0,
                "avg_error_after": round(float(cls_error_after / cls_weight), 4) if cls_weight > 0 else 0,
                "entropy_share": round(float(cls_weight), 4),
            }

    return {
        "seed_index": seed_idx,
        "score_no_obs": round(score_no_obs["score"], 2),
        "score_with_obs": round(score_with_obs["score"], 2),
        "observation_boost": round(score_with_obs["score"] - score_no_obs["score"], 2),
        "total_queries_on_seed": int(obs_total.sum()),
        "cells_queried": int(has_obs.sum()),
        "helpful_queries": len(helpful),
        "wasted_queries": len(wasted),
        "top_helpful": helpful[:20],
        "top_wasted": wasted[:10],
        "missed_opportunities": missed[:20],
        "optimal_overlap_pct": round(overlap_pct, 1),
        "terrain_summary": terrain_summary,
        "info_gain_map": info_gain.tolist(),
        "error_before_map": errors_no_obs.tolist(),
        "error_after_map": errors_with_obs.tolist(),
    }


def derive_rules(all_analyses):
    """Derive concrete query allocation rules from hindsight across rounds."""
    rules = []

    # Rule 1: Which terrain types benefit most from queries?
    terrain_gains = {}
    for analysis in all_analyses:
        for seed_result in analysis.get("seeds", []):
            for cls_name, summary in seed_result.get("terrain_summary", {}).items():
                if cls_name not in terrain_gains:
                    terrain_gains[cls_name] = {"gains": [], "errors": [], "queried_pcts": []}
                terrain_gains[cls_name]["gains"].append(summary["total_info_gain"])
                terrain_gains[cls_name]["errors"].append(summary["avg_error_before"])
                terrain_gains[cls_name]["queried_pcts"].append(summary["query_pct"])

    priority_order = sorted(terrain_gains.items(),
                             key=lambda x: -np.mean(x[1]["gains"]))
    for cls_name, data in priority_order:
        avg_gain = np.mean(data["gains"])
        avg_error = np.mean(data["errors"])
        avg_queried = np.mean(data["queried_pcts"])
        if avg_gain > 0.01:
            rules.append({
                "type": "query_priority",
                "terrain": cls_name,
                "avg_info_gain": round(float(avg_gain), 4),
                "avg_error_without_obs": round(float(avg_error), 4),
                "avg_query_coverage_pct": round(float(avg_queried), 1),
                "recommendation": f"Query {cls_name} cells: avg info gain {avg_gain:.3f}"
            })

    # Rule 2: Observation boost by seed position
    seed_boosts = {}
    for analysis in all_analyses:
        for seed_result in analysis.get("seeds", []):
            si = seed_result["seed_index"]
            if si not in seed_boosts:
                seed_boosts[si] = []
            seed_boosts[si].append(seed_result["observation_boost"])

    for si in sorted(seed_boosts):
        avg_boost = np.mean(seed_boosts[si])
        rules.append({
            "type": "seed_priority",
            "seed": si,
            "avg_observation_boost": round(float(avg_boost), 2),
            "recommendation": f"Seed {si}: avg boost from observations = {avg_boost:+.1f} points"
        })

    # Rule 3: Optimal overlap analysis
    overlaps = []
    for analysis in all_analyses:
        for seed_result in analysis.get("seeds", []):
            overlaps.append(seed_result["optimal_overlap_pct"])
    if overlaps:
        avg_overlap = np.mean(overlaps)
        rules.append({
            "type": "targeting_accuracy",
            "avg_optimal_overlap_pct": round(float(avg_overlap), 1),
            "recommendation": f"Our queries hit {avg_overlap:.0f}% of the highest-error cells. "
                            f"{'Good targeting.' if avg_overlap > 60 else 'Room for improvement: focus more on high-error areas.'}"
        })

    return rules


def build_replay(round_data, seed_idx, obs_counts, obs_total, ground_truth,
                  prediction, score):
    """Build a replay JSON for dashboard visualization."""
    h, w = round_data["map_height"], round_data["map_width"]
    ig = round_data["initial_states"][seed_idx]["grid"]
    gt = np.array(ground_truth)

    # Query heatmap: where we spent observations
    query_heatmap = obs_total.tolist() if obs_total is not None else None

    # Build argmax grids for easy visualization
    gt_argmax = gt.argmax(axis=-1).tolist()
    pred_argmax = np.array(prediction).argmax(axis=-1).tolist() if prediction is not None else None

    # Confidence map (max probability per cell)
    pred_arr = np.array(prediction)
    confidence = pred_arr.max(axis=-1).tolist() if prediction is not None else None

    # Diff: cells where prediction disagrees with ground truth
    diff = []
    if prediction is not None:
        for y in range(h):
            for x in range(w):
                gt_cls = int(gt_argmax[y][x])
                pred_cls = int(pred_argmax[y][x])
                if gt_cls != pred_cls:
                    diff.append({
                        "y": y, "x": x,
                        "predicted": CLASS_NAMES[pred_cls],
                        "actual": CLASS_NAMES[gt_cls],
                        "confidence": round(float(pred_arr[y, x, pred_cls]), 3),
                    })

    return {
        "seed_index": seed_idx,
        "initial_grid": ig,
        "ground_truth_argmax": gt_argmax,
        "ground_truth_probs": gt.tolist(),
        "prediction_argmax": pred_argmax,
        "prediction_confidence": confidence,
        "query_heatmap": query_heatmap,
        "score": round(float(score), 2),
        "diff_cells": diff[:50],
        "diff_count": len(diff),
    }


def run_hindsight(rounds_data, target_round=None):
    """Run hindsight analysis on all rounds with observation data."""
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)

    model = PredictionModel({
        "near_dist_1": 0.6, "near_dist_3": 0.4, "near_dist_5": 0.2,
        "forest_bonus_per_adj": 0.0, "forest_bonus_cap": 0.0,
    })

    all_analyses = []

    for rd in rounds_data:
        rn = rd["round_number"]
        if target_round is not None and rn != target_round:
            continue
        if not rd.get("seeds"):
            continue

        obs_data = load_real_observations(rn)
        if not obs_data:
            log(f"Round {rn}: no observation data, skipping")
            continue

        log(f"\n{'='*50}")
        log(f"  HINDSIGHT: Round {rn} (weight {rd.get('round_weight', 1.0):.4f})")
        log(f"{'='*50}")

        hist_trans = model.build_transitions(rounds_data, exclude_round=rn)
        round_trans = hist_trans  # fair: no oracle leakage

        round_analysis = {
            "round_number": rn,
            "round_weight": rd.get("round_weight", 1.0),
            "seeds": [],
            "replays": [],
        }

        for si_str, seed_gt in rd["seeds"].items():
            si = int(si_str)
            gt = np.array(seed_gt["ground_truth"])
            ig = rd["initial_states"][si]["grid"]

            obs_c, obs_t = None, None
            if si in obs_data:
                obs_c, obs_t = obs_data[si]

            if obs_c is not None:
                # Full hindsight analysis
                seed_analysis = analyze_query_value(
                    rd, si, obs_c, obs_t, seed_gt["ground_truth"],
                    model, hist_trans, round_trans
                )
                round_analysis["seeds"].append(seed_analysis)

                log(f"\n  Seed {si}: score {seed_analysis['score_no_obs']:.1f} -> "
                    f"{seed_analysis['score_with_obs']:.1f} "
                    f"(boost: {seed_analysis['observation_boost']:+.1f})")
                log(f"    Queries: {seed_analysis['cells_queried']} cells, "
                    f"{seed_analysis['helpful_queries']} helpful, "
                    f"{seed_analysis['wasted_queries']} wasted")
                log(f"    Optimal overlap: {seed_analysis['optimal_overlap_pct']:.0f}%")

                ts = seed_analysis.get("terrain_summary", {})
                for cls_name in ["Settlement", "Port", "Empty", "Forest"]:
                    if cls_name in ts:
                        t = ts[cls_name]
                        log(f"    {cls_name}: {t['queried']}/{t['cells']} queried, "
                            f"error {t['avg_error_before']:.3f}->{t['avg_error_after']:.3f}, "
                            f"gain {t['total_info_gain']:.3f}")

                # Build replay
                pred = model.predict_seed(rd, si, hist_trans, round_trans,
                                          obs_counts=obs_c, obs_total=obs_t)
                score_result = score_prediction(gt, pred, initial_grid=ig)
                replay = build_replay(rd, si, obs_c, obs_t,
                                       seed_gt["ground_truth"], pred.tolist(),
                                       score_result["score"])
                round_analysis["replays"].append(replay)
            else:
                # No observations for this seed, just build replay with model-only prediction
                pred = model.predict_seed(rd, si, hist_trans, round_trans)
                score_result = score_prediction(gt, pred, initial_grid=ig)
                replay = build_replay(rd, si, None, None,
                                       seed_gt["ground_truth"], pred.tolist(),
                                       score_result["score"])
                round_analysis["replays"].append(replay)
                log(f"\n  Seed {si}: no observations (model-only score: {score_result['score']:.1f})")

        # Compute missed opportunities across seeds
        if round_analysis["seeds"]:
            total_missed = sum(len(s.get("missed_opportunities", [])) for s in round_analysis["seeds"])
            total_helpful = sum(s["helpful_queries"] for s in round_analysis["seeds"])
            total_wasted = sum(s["wasted_queries"] for s in round_analysis["seeds"])
            log(f"\n  Round {rn} summary: {total_helpful} helpful, {total_wasted} wasted, "
                f"{total_missed} missed opportunities")

        all_analyses.append(round_analysis)

        # Save round hindsight
        hindsight_path = REPLAY_DIR / f"round_{rn}_hindsight.json"
        # Strip large maps from the saved JSON to keep file sizes reasonable
        save_analysis = {
            "round_number": rn,
            "round_weight": rd.get("round_weight", 1.0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seeds": [],
        }
        for seed_result in round_analysis["seeds"]:
            save_seed = {k: v for k, v in seed_result.items()
                        if k not in ("info_gain_map", "error_before_map", "error_after_map")}
            save_analysis["seeds"].append(save_seed)
        hindsight_path.write_text(json.dumps(save_analysis, indent=2))

        # Save replay
        replay_path = REPLAY_DIR / f"round_{rn}_replay.json"
        replay_path.write_text(json.dumps({
            "round_number": rn,
            "round_weight": rd.get("round_weight", 1.0),
            "map_height": rd["map_height"],
            "map_width": rd["map_width"],
            "seeds": round_analysis["replays"],
        }, indent=2))

        log(f"  Saved: {hindsight_path.name}, {replay_path.name}")

    # Derive rules from all analyses
    if all_analyses:
        rules = derive_rules(all_analyses)
        log(f"\n{'='*50}")
        log(f"  DERIVED RULES (from {len(all_analyses)} rounds)")
        log(f"{'='*50}")
        for rule in rules:
            log(f"  {rule['recommendation']}")

        rules_path = REPLAY_DIR / "query_rules.json"
        rules_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rounds_analyzed": len(all_analyses),
            "rules": rules,
        }, indent=2))
        log(f"  Saved: {rules_path.name}")

    # Save "latest" pointer for dashboard
    if all_analyses:
        latest = max(all_analyses, key=lambda a: a["round_number"])
        latest_path = REPLAY_DIR / "latest_round.json"
        latest_path.write_text(json.dumps({
            "round_number": latest["round_number"],
            "hindsight_file": f"round_{latest['round_number']}_hindsight.json",
            "replay_file": f"round_{latest['round_number']}_replay.json",
        }, indent=2))

    return all_analyses


def main():
    parser = argparse.ArgumentParser(description="Astar Island Hindsight Analyzer")
    parser.add_argument("--token", default=None)
    parser.add_argument("--cached-only", action="store_true")
    parser.add_argument("--round", type=int, default=None,
                        help="Analyze specific round only")
    args = parser.parse_args()

    if args.cached_only:
        from backtest import load_cached_rounds
        rounds_data = load_cached_rounds()
    else:
        if not args.token:
            log("--token required (or use --cached-only)")
            return
        session = get_session(args.token)
        import requests
        rounds = session.get(f"{BASE}/astar-island/rounds").json()
        completed = [r for r in rounds if r["status"] == "completed"]
        for r in sorted(completed, key=lambda r: r["round_number"]):
            cache_round(session, r)
        rounds_data = load_cached_rounds()

    if not rounds_data:
        log("No rounds data available.")
        return

    log(f"Hindsight analysis on {len(rounds_data)} rounds")
    run_hindsight(rounds_data, target_round=args.round)


if __name__ == "__main__":
    main()
