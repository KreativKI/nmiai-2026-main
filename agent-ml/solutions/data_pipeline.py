#!/usr/bin/env python3
"""
Data Pipeline: runs after every round to cache, extract, and sync data.

Does everything needed to keep the ML pipeline fed:
1. Cache ground truth for completed rounds
2. Download replays (FREE) for completed rounds
3. Build/update master dataset
4. Upload to GCP for churn/model training

Idempotent: safe to run multiple times. Skips already-cached data.

Usage:
  python data_pipeline.py --token TOKEN                    # Process all pending rounds
  python data_pipeline.py --token TOKEN --round 16         # Process specific round
  python data_pipeline.py --token TOKEN --sync-gcp         # Also upload to GCP
  python data_pipeline.py --token TOKEN --rebuild-dataset   # Force rebuild master dataset
"""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import requests

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import get_session, cache_round, load_cached_rounds, BASE
from build_dataset import build_master_dataset, FEATURE_NAMES

DATA_DIR = Path(__file__).parent / "data"
REPLAY_DIR = DATA_DIR / "replays"
GT_DIR = DATA_DIR / "ground_truth_cache"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def cache_ground_truth(session, round_data):
    """Cache ground truth if not already cached."""
    rn = round_data["round_number"]
    gt_path = GT_DIR / f"round_{rn}.json"
    if gt_path.exists():
        return False  # Already cached
    log(f"  Caching R{rn} ground truth...")
    cache_round(session, round_data)
    return True


def download_replays(session, round_data):
    """Download replay for all 5 seeds if not already cached."""
    rn = round_data["round_number"]
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for si in range(5):
        path = REPLAY_DIR / f"r{rn}_seed{si}.json"
        if path.exists():
            continue
        try:
            r = session.post(f"{BASE}/astar-island/replay", json={
                "round_id": round_data["id"], "seed_index": si
            })
            if r.status_code == 200:
                with open(path, "w") as f:
                    json.dump(r.json(), f)
                downloaded += 1
            elif r.status_code == 429:
                log(f"  R{rn} seed {si}: rate limited, waiting...")
                time.sleep(3)
                r = session.post(f"{BASE}/astar-island/replay", json={
                    "round_id": round_data["id"], "seed_index": si
                })
                if r.status_code == 200:
                    with open(path, "w") as f:
                        json.dump(r.json(), f)
                    downloaded += 1
            time.sleep(0.5)
        except Exception as e:
            log(f"  R{rn} seed {si} replay failed: {e}")
    if downloaded > 0:
        log(f"  R{rn}: {downloaded} replays downloaded")
    return downloaded


def get_round_score(session, round_number):
    """Get our score for a specific round."""
    my_rounds = session.get(f"{BASE}/astar-island/my-rounds").json()
    for rd in my_rounds:
        if rd.get("round_number") == round_number:
            return {
                "score": rd.get("round_score"),
                "rank": rd.get("rank"),
                "weighted": rd.get("round_score", 0) * rd.get("round_weight", 0),
                "seeds": rd.get("seed_scores", []),
                "weight": rd.get("round_weight", 0),
            }
    return None


def sync_to_gcp(vm_name="ml-churn", zone="europe-west1-b", project="ai-nm26osl-1779"):
    """Upload master dataset and new ground truth to GCP."""
    import subprocess

    dataset_path = DATA_DIR / "master_dataset.npz"
    if dataset_path.exists():
        log(f"  Syncing master dataset to {vm_name}...")
        subprocess.run([
            "gcloud", "compute", "scp",
            str(dataset_path),
            f"{vm_name}:~/solutions/data/master_dataset.npz",
            f"--zone={zone}", f"--project={project}",
        ], capture_output=True)

    # Sync ground truth cache
    for gt_file in GT_DIR.glob("round_*.json"):
        subprocess.run([
            "gcloud", "compute", "scp",
            str(gt_file),
            f"{vm_name}:~/solutions/data/ground_truth_cache/{gt_file.name}",
            f"--zone={zone}", f"--project={project}",
        ], capture_output=True)

    log(f"  Synced to {vm_name}")


def process_round(session, round_data, rebuild_dataset=False, do_sync=False):
    """Full pipeline for one completed round."""
    rn = round_data["round_number"]
    log(f"Processing R{rn}...")

    # Step 1: Cache ground truth
    new_gt = cache_ground_truth(session, round_data)

    # Step 2: Download replays
    new_replays = download_replays(session, round_data)

    # Step 3: Get and log score
    score_info = get_round_score(session, rn)
    if score_info and score_info["score"]:
        log(f"  R{rn} score: {score_info['score']:.1f} rank={score_info['rank']} "
            f"weighted={score_info['weighted']:.1f}")

    # Step 4: Rebuild master dataset if new data
    if new_gt or new_replays or rebuild_dataset:
        log("  Building master dataset...")
        X, Y, meta = build_master_dataset()
        np.savez_compressed(DATA_DIR / "master_dataset.npz", X=X, Y=Y)
        with open(DATA_DIR / "master_dataset_features.json", "w") as f:
            json.dump(FEATURE_NAMES, f, indent=2)
        log(f"  Master dataset: {len(X)} rows, {len(FEATURE_NAMES)} features")

    # Step 5: Sync to GCP
    if do_sync:
        sync_to_gcp()

    return {"new_gt": new_gt, "new_replays": new_replays, "score": score_info}


def main():
    parser = argparse.ArgumentParser(description="ML Data Pipeline")
    parser.add_argument("--token", required=True)
    parser.add_argument("--round", type=int, help="Process specific round")
    parser.add_argument("--sync-gcp", action="store_true")
    parser.add_argument("--rebuild-dataset", action="store_true")
    args = parser.parse_args()

    session = get_session(args.token)

    # Get all rounds
    rounds = session.get(f"{BASE}/astar-island/rounds").json()
    completed = [r for r in rounds if r["status"] == "completed"]
    completed.sort(key=lambda x: x["round_number"])

    if args.round:
        # Process specific round
        target = [r for r in completed if r["round_number"] == args.round]
        if not target:
            log(f"R{args.round} not found or not completed")
            return
        process_round(session, target[0], args.rebuild_dataset, args.sync_gcp)
    else:
        # Process all completed rounds (skip already cached)
        processed = 0
        for rd in completed:
            result = process_round(session, rd, args.rebuild_dataset, args.sync_gcp)
            if result["new_gt"] or result["new_replays"]:
                processed += 1

        if processed == 0 and not args.rebuild_dataset:
            log("All rounds already cached. Use --rebuild-dataset to force rebuild.")
        else:
            log(f"\nProcessed {processed} rounds. Total cached: {len(list(GT_DIR.glob('round_*.json')))}")

    # Always show current state
    log(f"\nData state:")
    log(f"  Ground truth: {len(list(GT_DIR.glob('round_*.json')))} rounds")
    log(f"  Replays: {len(list(REPLAY_DIR.glob('r*_seed*.json')))} files")
    dataset_path = DATA_DIR / "master_dataset.npz"
    if dataset_path.exists():
        d = np.load(dataset_path)
        log(f"  Master dataset: {d['X'].shape[0]} rows, {d['X'].shape[1]} features")


if __name__ == "__main__":
    main()
