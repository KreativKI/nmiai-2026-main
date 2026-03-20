#!/usr/bin/env python3
"""
Astar Island Backtester — Offline QC gate for model changes.

Fetches ground truth from completed rounds, replays prediction logic,
scores against truth using the official formula, and reports breakdowns.

Usage:
  # Score current model against all completed rounds
  python backtest.py --token TOKEN

  # Score with tweaked parameters (A/B test)
  python backtest.py --token TOKEN --obs-weight-settle 0.8 --hist-blend 0.15

  # Compare two configs
  python backtest.py --token TOKEN --compare

  # Only test specific rounds
  python backtest.py --token TOKEN --rounds 4,5,6

  # Cache ground truth locally (avoids repeated API calls)
  python backtest.py --token TOKEN --cache

  # Use cached data only (no API calls)
  python backtest.py --cached-only
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import requests

BASE = "https://api.ainm.no"
DATA_DIR = Path(__file__).parent / "data"
CACHE_DIR = DATA_DIR / "ground_truth_cache"

TERRAIN_TO_CLASS = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 10: 0, 11: 0}
STATIC_TERRAIN = {5, 10}
NUM_CLASSES = 6
PROB_FLOOR = 0.01
CLASS_NAMES = ["Empty", "Settlement", "Port", "Ruin", "Forest", "Mountain"]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_session(token: str) -> requests.Session:
    s = requests.Session()
    s.cookies.set("access_token", token, domain="api.ainm.no")
    s.headers["User-Agent"] = "astar-backtest/nmiai-2026"
    return s


# ──────────────────────────────────────────────
# Ground Truth Fetching & Caching
# ──────────────────────────────────────────────

def fetch_ground_truth(session, round_info, seed_idx):
    """Fetch ground truth for one seed from /analysis endpoint."""
    resp = session.get(f"{BASE}/astar-island/analysis/{round_info['id']}/{seed_idx}")
    if resp.status_code != 200:
        return None
    return resp.json()


def cache_round(session, round_info):
    """Cache all ground truth for a completed round."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    rn = round_info["round_number"]
    detail = session.get(f"{BASE}/astar-island/rounds/{round_info['id']}").json()

    cache_path = CACHE_DIR / f"round_{rn}.json"
    if cache_path.exists():
        log(f"  Round {rn}: already cached")
        return json.loads(cache_path.read_text())

    round_data = {
        "round_number": rn,
        "round_id": round_info["id"],
        "round_weight": round_info["round_weight"],
        "map_height": detail["map_height"],
        "map_width": detail["map_width"],
        "seeds_count": detail.get("seeds_count", 5),
        "initial_states": detail["initial_states"],
        "seeds": {},
    }

    for si in range(round_data["seeds_count"]):
        gt = fetch_ground_truth(session, round_info, si)
        if gt is None:
            log(f"  Round {rn} seed {si}: no ground truth available")
            continue
        round_data["seeds"][str(si)] = gt
        time.sleep(0.2)

    cache_path.write_text(json.dumps(round_data))
    log(f"  Round {rn}: cached {len(round_data['seeds'])} seeds")
    return round_data


def load_cached_rounds():
    """Load all cached ground truth."""
    if not CACHE_DIR.exists():
        return []
    rounds = []
    for p in sorted(CACHE_DIR.glob("round_*.json")):
        rounds.append(json.loads(p.read_text()))
    return rounds


# ──────────────────────────────────────────────
# Scoring (official formula)
# ──────────────────────────────────────────────

def kl_divergence(gt_dist, pred_dist):
    """KL(gt || pred) for a single cell. gt_dist and pred_dist are 1D arrays summing to 1."""
    gt = np.asarray(gt_dist, dtype=np.float64)
    pred = np.asarray(pred_dist, dtype=np.float64)
    pred = np.maximum(pred, 1e-10)
    gt = np.maximum(gt, 1e-10)
    mask = gt > 1e-8
    return np.sum(gt[mask] * np.log(gt[mask] / pred[mask]))


def entropy(dist):
    """Shannon entropy of a distribution."""
    d = np.asarray(dist, dtype=np.float64)
    d = np.maximum(d, 1e-10)
    return -np.sum(d * np.log(d))


def score_prediction(ground_truth_grid, prediction, initial_grid=None):
    """
    Score a prediction against ground truth using entropy-weighted KL divergence.

    Args:
        ground_truth_grid: H x W x 6 probability distributions (from /analysis)
        prediction: H x W x 6 probability distributions (our model output)
        initial_grid: H x W raw terrain values (for static/dynamic breakdown)

    Returns:
        dict with score, weighted_kl, and per-class breakdowns
    """
    gt = np.asarray(ground_truth_grid, dtype=np.float64)
    pred = np.asarray(prediction, dtype=np.float64)
    h, w, c = gt.shape

    total_weighted_kl = 0.0
    total_entropy = 0.0
    class_kl = np.zeros(NUM_CLASSES)
    class_entropy = np.zeros(NUM_CLASSES)
    class_count = np.zeros(NUM_CLASSES)
    cell_scores = np.zeros((h, w))

    for y in range(h):
        for x in range(w):
            ent = entropy(gt[y, x])
            if ent < 1e-8:
                continue
            kl = kl_divergence(gt[y, x], pred[y, x])
            total_weighted_kl += ent * kl
            total_entropy += ent
            cell_scores[y, x] = kl

            if initial_grid is not None:
                cls = TERRAIN_TO_CLASS.get(int(initial_grid[y][x]), 0)
                class_kl[cls] += ent * kl
                class_entropy[cls] += ent
                class_count[cls] += 1

    if total_entropy < 1e-8:
        weighted_kl = 0.0
    else:
        weighted_kl = total_weighted_kl / total_entropy

    score = max(0, min(100, 100 * np.exp(-3 * weighted_kl)))

    result = {
        "score": score,
        "weighted_kl": weighted_kl,
        "total_entropy": total_entropy,
        "cell_scores": cell_scores,
    }

    if initial_grid is not None:
        result["per_class"] = {}
        for i, name in enumerate(CLASS_NAMES):
            if class_entropy[i] > 1e-8:
                cls_wkl = class_kl[i] / class_entropy[i]
                result["per_class"][name] = {
                    "weighted_kl": cls_wkl,
                    "score": max(0, min(100, 100 * np.exp(-3 * cls_wkl))),
                    "entropy_share": class_entropy[i] / total_entropy,
                    "cell_count": int(class_count[i]),
                }

    return result


# ──────────────────────────────────────────────
# Prediction Model (mirrors astar_v6 logic)
# ──────────────────────────────────────────────

class PredictionModel:
    """Configurable prediction model for backtesting.

    Params dict controls model behavior:
        prob_floor: minimum probability (default 0.01)
        hist_blend: weight for historical transitions vs round-specific (default 0.1)
        obs_weight_settle: max observation weight for settlements (default 0.95)
        obs_weight_forest: max observation weight for forests (default 0.4)
        obs_weight_empty: max observation weight for empty/plains (default 0.35)
        forest_bonus_per_adj: settlement survival boost per adjacent forest (default 0.02)
        forest_bonus_cap: max settlement survival boost from forests (default 0.08)
        near_dist_1: weight for near transitions at distance 1 (default 0.8)
        near_dist_3: weight for near transitions at distance 3 (default 0.6)
        near_dist_5: weight for near transitions at distance 5 (default 0.3)
    """

    DEFAULT_PARAMS = {
        "prob_floor": 0.01,
        "hist_blend": 0.1,
        "obs_weight_settle": 0.95,
        "obs_weight_forest": 0.4,
        "obs_weight_empty": 0.35,
        "forest_bonus_per_adj": 0.02,
        "forest_bonus_cap": 0.08,
        "near_dist_1": 0.8,
        "near_dist_3": 0.6,
        "near_dist_5": 0.3,
    }

    def __init__(self, params=None):
        self.params = dict(self.DEFAULT_PARAMS)
        if params:
            self.params.update(params)

    def build_transitions(self, completed_rounds, exclude_round=None):
        """Build transition matrices from ground truth of completed rounds.

        If exclude_round is set, that round is excluded (for cross-validation).
        Returns dict with global/near/far transition matrices.
        """
        sums = {k: np.zeros((NUM_CLASSES, NUM_CLASSES)) for k in ["global", "near", "far"]}
        counts = {k: np.zeros(NUM_CLASSES) for k in ["global", "near", "far"]}

        for rd in completed_rounds:
            if exclude_round is not None and rd["round_number"] == exclude_round:
                continue
            h = rd["map_height"]
            w = rd["map_width"]
            for si_str, seed_data in rd["seeds"].items():
                ig = rd["initial_states"][int(si_str)]["grid"]
                gt = np.array(seed_data["ground_truth"])
                for y in range(h):
                    for x in range(w):
                        cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                        sums["global"][cls] += gt[y][x]
                        counts["global"][cls] += 1
                        has_adj = any(
                            0 <= y+dy < h and 0 <= x+dx < w
                            and TERRAIN_TO_CLASS.get(ig[y+dy][x+dx], 0) in (1, 2)
                            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if (dy, dx) != (0, 0)
                        )
                        key = "near" if has_adj else "far"
                        sums[key][cls] += gt[y][x]
                        counts[key][cls] += 1

        floor = self.params["prob_floor"]

        def normalize(s, c):
            mat = np.full((NUM_CLASSES, NUM_CLASSES), floor)
            for i in range(NUM_CLASSES):
                if c[i] > 0:
                    mat[i] = s[i] / c[i]
            mat = np.maximum(mat, floor)
            return mat / mat.sum(axis=1, keepdims=True)

        return {k: normalize(sums[k], counts[k]) for k in ["global", "near", "far"]}

    def build_round_transitions(self, round_data, observation_seeds=None):
        """Build transition matrices from observations within a single round.

        observation_seeds: dict of {seed_idx: (obs_counts, obs_total)} arrays
        If None, uses ground truth as "perfect observations" (for backtesting upper bound).
        """
        p = self.params
        h, w = round_data["map_height"], round_data["map_width"]

        sums = {k: np.zeros((NUM_CLASSES, NUM_CLASSES)) for k in ["global", "near", "far"]}
        counts = {k: np.zeros(NUM_CLASSES) for k in ["global", "near", "far"]}

        if observation_seeds is None:
            # Use ground truth directly (simulates having observed everything)
            for si_str, seed_data in round_data["seeds"].items():
                ig = round_data["initial_states"][int(si_str)]["grid"]
                gt = np.array(seed_data["ground_truth"])
                for y in range(h):
                    for x in range(w):
                        cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                        sums["global"][cls] += gt[y][x]
                        counts["global"][cls] += 1
                        has_adj = any(
                            0 <= y+dy < h and 0 <= x+dx < w
                            and TERRAIN_TO_CLASS.get(ig[y+dy][x+dx], 0) in (1, 2)
                            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if (dy, dx) != (0, 0)
                        )
                        key = "near" if has_adj else "far"
                        sums[key][cls] += gt[y][x]
                        counts[key][cls] += 1
        else:
            for seed_idx, (oc, ot) in observation_seeds.items():
                si_str = str(seed_idx)
                if si_str not in round_data["seeds"]:
                    continue
                ig = round_data["initial_states"][seed_idx]["grid"]
                for y in range(h):
                    for x in range(w):
                        if ot[y, x] == 0:
                            continue
                        cls = TERRAIN_TO_CLASS.get(int(ig[y][x]), 0)
                        empirical = oc[y, x] / ot[y, x]
                        sums["global"][cls] += empirical
                        counts["global"][cls] += 1
                        has_adj = any(
                            0 <= y+dy < h and 0 <= x+dx < w
                            and TERRAIN_TO_CLASS.get(ig[y+dy][x+dx], 0) in (1, 2)
                            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                            if (dy, dx) != (0, 0)
                        )
                        key = "near" if has_adj else "far"
                        sums[key][cls] += empirical
                        counts[key][cls] += 1

        floor = self.params["prob_floor"]

        def normalize(s, c):
            mat = np.full((NUM_CLASSES, NUM_CLASSES), floor)
            for i in range(NUM_CLASSES):
                if c[i] > 0:
                    mat[i] = s[i] / c[i]
            mat = np.maximum(mat, floor)
            return mat / mat.sum(axis=1, keepdims=True)

        return {k: normalize(sums[k], counts[k]) for k in ["global", "near", "far"]}

    def predict_seed(self, round_data, seed_idx, hist_trans, round_trans,
                     obs_counts=None, obs_total=None):
        """Generate prediction for one seed. Mirrors astar_v6 phase_submit logic."""
        p = self.params
        h, w = round_data["map_height"], round_data["map_width"]
        grid = round_data["initial_states"][seed_idx]["grid"]
        floor = p["prob_floor"]

        # Blend historical and round-specific transitions
        blend_w = 1.0 - p["hist_blend"]
        final_trans = {}
        for k in ["global", "near", "far"]:
            final_trans[k] = blend_w * round_trans[k] + (1 - blend_w) * hist_trans[k]
            final_trans[k] = np.maximum(final_trans[k], floor)
            final_trans[k] = final_trans[k] / final_trans[k].sum(axis=1, keepdims=True)

        # Precompute settlement positions and distance map
        settlement_positions = []
        for y in range(h):
            for x in range(w):
                if TERRAIN_TO_CLASS.get(grid[y][x], 0) in (1, 2):
                    settlement_positions.append((y, x))

        dist_map = np.full((h, w), 99)
        for sy, sx in settlement_positions:
            for y in range(h):
                for x in range(w):
                    d = abs(y - sy) + abs(x - sx)
                    dist_map[y, x] = min(dist_map[y, x], d)

        pred = np.full((h, w, NUM_CLASSES), floor)

        for y in range(h):
            for x in range(w):
                terrain = grid[y][x]
                cls = TERRAIN_TO_CLASS.get(terrain, 0)

                if terrain in STATIC_TERRAIN:
                    pred[y, x] = final_trans["global"][cls]
                    continue

                dist = dist_map[y, x]
                if dist <= 1:
                    w_near = p["near_dist_1"]
                elif dist <= 3:
                    w_near = p["near_dist_3"]
                elif dist <= 5:
                    w_near = p["near_dist_5"]
                else:
                    w_near = 0.0

                adj_forests = sum(
                    1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy, dx) != (0, 0)
                    and 0 <= y+dy < h and 0 <= x+dx < w
                    and TERRAIN_TO_CLASS.get(grid[y+dy][x+dx], 0) == 4
                )

                base = w_near * final_trans["near"][cls] + \
                       (1 - w_near) * final_trans["far"][cls]

                if cls == 1 and adj_forests > 0:
                    fb = min(adj_forests * p["forest_bonus_per_adj"], p["forest_bonus_cap"])
                    base[1] += fb
                    base[0] -= fb * 0.6
                    base[4] -= fb * 0.4

                pred[y, x] = base

        # Blend with observations if available
        if obs_counts is not None and obs_total is not None:
            ot = obs_total
            oc = obs_counts
            has_obs = ot > 0
            if has_obs.any():
                ot_3d = ot[..., np.newaxis]
                empirical = oc / np.maximum(ot_3d, 1)

                obs_w = np.zeros((h, w, 1))
                for y in range(h):
                    for x in range(w):
                        if ot[y, x] == 0:
                            continue
                        terrain = grid[y][x]
                        cls = TERRAIN_TO_CLASS.get(terrain, 0)
                        n = ot[y, x]
                        if cls in (1, 2, 3):
                            obs_w[y, x, 0] = min(p["obs_weight_settle"], 0.5 + n / 15.0)
                        elif cls == 4:
                            obs_w[y, x, 0] = min(p["obs_weight_forest"], 0.1 + n / 20.0)
                        else:
                            obs_w[y, x, 0] = min(p["obs_weight_empty"], 0.1 + n / 25.0)

                pred = np.where(
                    has_obs[..., np.newaxis],
                    obs_w * empirical + (1 - obs_w) * pred,
                    pred
                )

        # Floor and renormalize
        pred = np.maximum(pred, floor)
        pred = pred / pred.sum(axis=-1, keepdims=True)
        return pred


# ──────────────────────────────────────────────
# Backtest Runner
# ──────────────────────────────────────────────

def run_backtest(rounds_data, model, mode="leave_one_out", observation_seeds_map=None):
    """
    Run backtesting across rounds.

    mode:
        "leave_one_out": For each round, build hist transitions from OTHER rounds,
                         use ground truth as "perfect observations" for round transitions.
        "hist_only": Use all historical transitions, no round-specific observations.
        "with_obs": Use actual observation data from observation_seeds_map.
    """
    results = []

    for rd in rounds_data:
        rn = rd["round_number"]
        if not rd.get("seeds"):
            continue

        if mode == "oracle":
            # Upper bound: uses round's own ground truth as perfect observations
            hist_trans = model.build_transitions(rounds_data, exclude_round=rn)
            round_trans = model.build_round_transitions(rd, observation_seeds=None)
        elif mode == "leave_one_out":
            # Fair test: historical transitions only, current round excluded
            hist_trans = model.build_transitions(rounds_data, exclude_round=rn)
            round_trans = hist_trans
        elif mode == "hist_only":
            hist_trans = model.build_transitions(rounds_data, exclude_round=rn)
            round_trans = hist_trans
        elif mode == "with_obs":
            hist_trans = model.build_transitions(rounds_data, exclude_round=rn)
            obs_seeds = observation_seeds_map.get(rn, {}) if observation_seeds_map else {}
            if obs_seeds:
                round_trans = model.build_round_transitions(rd, observation_seeds=obs_seeds)
            else:
                round_trans = hist_trans

        round_scores = []
        for si_str, seed_data in rd["seeds"].items():
            si = int(si_str)
            ig = rd["initial_states"][si]["grid"]
            gt = np.array(seed_data["ground_truth"])

            obs_c, obs_t = None, None
            if mode == "with_obs" and observation_seeds_map:
                obs_map = observation_seeds_map.get(rn, {})
                if si in obs_map:
                    obs_c, obs_t = obs_map[si]

            pred = model.predict_seed(rd, si, hist_trans, round_trans,
                                      obs_counts=obs_c, obs_total=obs_t)
            score_result = score_prediction(gt, pred, initial_grid=ig)
            score_result["seed_index"] = si
            score_result["round_number"] = rn
            round_scores.append(score_result)

        avg_score = np.mean([s["score"] for s in round_scores])
        results.append({
            "round_number": rn,
            "round_weight": rd.get("round_weight", 1.0),
            "avg_score": avg_score,
            "seed_scores": round_scores,
        })

    return results


def print_results(results, label=""):
    """Pretty-print backtest results."""
    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

    for r in results:
        rn = r["round_number"]
        avg = r["avg_score"]
        seeds = ", ".join(f"s{s['seed_index']}:{s['score']:.1f}" for s in r["seed_scores"])
        print(f"\n  Round {rn} (weight {r['round_weight']:.4f}): avg {avg:.1f}  [{seeds}]")

        # Per-class breakdown (average across seeds)
        class_data = {}
        for s in r["seed_scores"]:
            for cls_name, cls_info in s.get("per_class", {}).items():
                if cls_name not in class_data:
                    class_data[cls_name] = []
                class_data[cls_name].append(cls_info)

        if class_data:
            print(f"    {'Class':<12} {'KL':>6} {'Score':>6} {'Entropy%':>9} {'Cells':>6}")
            print(f"    {'-'*12} {'-'*6} {'-'*6} {'-'*9} {'-'*6}")
            for cls_name in CLASS_NAMES:
                if cls_name not in class_data:
                    continue
                entries = class_data[cls_name]
                avg_kl = np.mean([e["weighted_kl"] for e in entries])
                avg_sc = np.mean([e["score"] for e in entries])
                avg_ent = np.mean([e["entropy_share"] for e in entries]) * 100
                avg_cnt = np.mean([e["cell_count"] for e in entries])
                print(f"    {cls_name:<12} {avg_kl:>6.3f} {avg_sc:>6.1f} {avg_ent:>8.1f}% {avg_cnt:>6.0f}")

    # Summary
    all_scores = [r["avg_score"] for r in results]
    if all_scores:
        best = max(all_scores)
        avg = np.mean(all_scores)
        print(f"\n  SUMMARY: best={best:.1f}, avg={avg:.1f}, rounds={len(results)}")


def load_real_observations(round_num):
    """Load actual observation data saved during live rounds."""
    obs_seeds = {}
    for label_seed in [
        (0, "seed0_stacked"), (0, "seed0_overview"),
        (1, "seed1"), (2, "seed2")
    ]:
        seed_idx, label = label_seed
        p_counts = DATA_DIR / f"obs_counts_r{round_num}_{label}.npy"
        p_total = DATA_DIR / f"obs_total_r{round_num}_{label}.npy"
        if p_counts.exists() and p_total.exists():
            oc = np.load(p_counts)
            ot = np.load(p_total)
            if seed_idx in obs_seeds:
                # Use whichever file has more data (stacked includes overview)
                prev_oc, prev_ot = obs_seeds[seed_idx]
                if ot.sum() > prev_ot.sum():
                    obs_seeds[seed_idx] = (oc.copy(), ot.copy())
            else:
                obs_seeds[seed_idx] = (oc.copy(), ot.copy())
    return obs_seeds


def main():
    parser = argparse.ArgumentParser(description="Astar Island Backtester")
    parser.add_argument("--token", default=None,
                        help="JWT token (required unless --cached-only)")
    parser.add_argument("--cache", action="store_true",
                        help="Fetch and cache ground truth from API")
    parser.add_argument("--cached-only", action="store_true",
                        help="Use cached data only, no API calls")
    parser.add_argument("--rounds", type=str, default=None,
                        help="Comma-separated round numbers to test (default: all)")
    parser.add_argument("--compare", action="store_true",
                        help="Run A/B comparison between default and tweaked params")
    parser.add_argument("--with-obs", action="store_true",
                        help="Include actual observation data from live rounds")

    # Tunable params
    parser.add_argument("--hist-blend", type=float, default=None)
    parser.add_argument("--obs-weight-settle", type=float, default=None)
    parser.add_argument("--obs-weight-forest", type=float, default=None)
    parser.add_argument("--obs-weight-empty", type=float, default=None)
    parser.add_argument("--forest-bonus-per-adj", type=float, default=None)
    parser.add_argument("--forest-bonus-cap", type=float, default=None)
    parser.add_argument("--near-dist-1", type=float, default=None)
    parser.add_argument("--near-dist-3", type=float, default=None)
    parser.add_argument("--near-dist-5", type=float, default=None)

    args = parser.parse_args()

    # Load or fetch ground truth
    if args.cached_only:
        rounds_data = load_cached_rounds()
        if not rounds_data:
            log("No cached data found. Run with --cache first.")
            return
    else:
        if not args.token:
            log("--token required (or use --cached-only)")
            return
        session = get_session(args.token)

        if args.cache or not CACHE_DIR.exists():
            log("Fetching ground truth from API...")
            rounds = session.get(f"{BASE}/astar-island/rounds").json()
            completed = [r for r in rounds if r["status"] == "completed"]
            for r in sorted(completed, key=lambda r: r["round_number"]):
                cache_round(session, r)

        rounds_data = load_cached_rounds()
        if not rounds_data:
            log("No completed rounds with ground truth available.")
            return

    # Filter rounds if specified
    if args.rounds:
        target_rounds = set(int(x) for x in args.rounds.split(","))
        rounds_data = [rd for rd in rounds_data if rd["round_number"] in target_rounds]

    log(f"Backtesting against {len(rounds_data)} rounds: "
        f"{[rd['round_number'] for rd in rounds_data]}")

    # Load observation data if requested
    observation_seeds_map = None
    if args.with_obs:
        observation_seeds_map = {}
        for rd in rounds_data:
            obs = load_real_observations(rd["round_number"])
            if obs:
                observation_seeds_map[rd["round_number"]] = obs
                log(f"  Loaded observations for round {rd['round_number']}: "
                    f"seeds {list(obs.keys())}")

    # Build param overrides
    param_overrides = {}
    for key in ["hist_blend", "obs_weight_settle", "obs_weight_forest",
                "obs_weight_empty", "forest_bonus_per_adj", "forest_bonus_cap",
                "near_dist_1", "near_dist_3", "near_dist_5"]:
        val = getattr(args, key.replace("-", "_"))
        if val is not None:
            param_overrides[key] = val

    if args.compare:
        # A/B comparison
        model_a = PredictionModel()
        model_b = PredictionModel(param_overrides if param_overrides else {
            "hist_blend": 0.05,
            "obs_weight_settle": 0.90,
            "near_dist_1": 0.9,
        })

        mode = "with_obs" if args.with_obs else "leave_one_out"
        results_a = run_backtest(rounds_data, model_a, mode=mode,
                                 observation_seeds_map=observation_seeds_map)
        results_b = run_backtest(rounds_data, model_b, mode=mode,
                                 observation_seeds_map=observation_seeds_map)

        print_results(results_a, "MODEL A (default)")
        print_results(results_b, "MODEL B (tweaked)")

        # Delta
        print(f"\n{'='*60}")
        print(f"  COMPARISON")
        print(f"{'='*60}")
        for ra, rb in zip(results_a, results_b):
            delta = rb["avg_score"] - ra["avg_score"]
            sign = "+" if delta >= 0 else ""
            print(f"  Round {ra['round_number']}: A={ra['avg_score']:.1f} "
                  f"B={rb['avg_score']:.1f} delta={sign}{delta:.1f}")

        all_a = np.mean([r["avg_score"] for r in results_a])
        all_b = np.mean([r["avg_score"] for r in results_b])
        delta = all_b - all_a
        sign = "+" if delta >= 0 else ""
        print(f"\n  OVERALL: A={all_a:.1f} B={all_b:.1f} delta={sign}{delta:.1f}")
    else:
        # Single model run
        model = PredictionModel(param_overrides if param_overrides else None)

        # Run modes for comparison: baseline, fair test, oracle ceiling
        modes_to_run = ["hist_only", "leave_one_out", "oracle"]
        if args.with_obs:
            modes_to_run.append("with_obs")

        for mode in modes_to_run:
            results = run_backtest(rounds_data, model, mode=mode,
                                   observation_seeds_map=observation_seeds_map)
            labels = {
                "hist_only": "HIST ONLY (no round info, current round excluded)",
                "leave_one_out": "LEAVE-ONE-OUT (hist from other rounds, no round obs)",
                "oracle": "ORACLE (round GT as perfect obs, upper bound)",
                "with_obs": "WITH REAL OBSERVATIONS (actual query data)",
            }
            print_results(results, labels[mode])


if __name__ == "__main__":
    main()
