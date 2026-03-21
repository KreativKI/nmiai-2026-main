#!/usr/bin/env python3
"""
Model C: CA-Markov Forward Simulation.

Chains neighborhood-conditioned transition matrices forward 50 steps
to predict year-50 terrain probability distributions.

Uses transition_model.py for the learned transition probabilities.

Usage:
  python model_c_camarkov.py              # Evaluate with leave-one-round-out CV
"""

import argparse
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (
    load_cached_rounds, TERRAIN_TO_CLASS, STATIC_TERRAIN, NUM_CLASSES, PROB_FLOOR,
)
from transition_model import TransitionModel, SKIP_CELLS, OCEAN_RAW
from evaluate import evaluate_leave_one_out


STEPS = 50


class ModelCCAMarkov:
    """CA-Markov: chain transition matrices forward 50 steps."""

    def __init__(self):
        self.tm = None

    def train(self, rounds_data, exclude_round=None):
        from transition_model import build_transition_tables, normalize_tables, REPLAY_DIR
        raw = build_transition_tables(REPLAY_DIR, rounds_data)
        self.tm = TransitionModel(tables=normalize_tables(raw))

    def predict(self, round_data, seed_idx, regime):
        h, w = round_data["map_height"], round_data["map_width"]
        ig = round_data["initial_states"][seed_idx]["grid"]
        pred = np.zeros((h, w, NUM_CLASSES))

        for y in range(h):
            for x in range(w):
                raw = int(ig[y][x])

                # Static cells: near-certain self-prediction
                if raw in SKIP_CELLS:
                    cls = TERRAIN_TO_CLASS.get(raw, 0)
                    pred[y, x] = PROB_FLOOR
                    pred[y, x, cls] = 1.0 - (NUM_CLASSES - 1) * PROB_FLOOR
                    continue

                cls = TERRAIN_TO_CLASS.get(raw, 0)

                # Empty cells: neighbor-density heuristic
                if cls == 0:
                    pred[y, x] = self._empty_cell_prior(ig, y, x, h, w, regime)
                    continue

                # Dynamic cells: chain transition matrix forward
                n_settle, n_forest = self._count_neighbors(ig, y, x, h, w)
                pred[y, x] = self._chain_forward(regime, cls, n_settle, n_forest)

        return pred

    def _count_neighbors(self, grid, y, x, h, w):
        n_settle, n_forest = 0, 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w:
                    c = TERRAIN_TO_CLASS.get(int(grid[ny][nx]), 0)
                    if c in (1, 2):
                        n_settle += 1
                    elif c == 4:
                        n_forest += 1
        return n_settle, n_forest

    def _chain_forward(self, regime, start_cls, n_settle, n_forest):
        """Chain transition probabilities forward STEPS times.

        State is a probability distribution [6]. At each step, multiply
        by the transition matrix to get the next distribution.
        """
        state = np.zeros(NUM_CLASSES)
        state[start_cls] = 1.0

        for _ in range(STEPS):
            next_state = np.zeros(NUM_CLASSES)
            for from_cls in range(NUM_CLASSES):
                if state[from_cls] < 1e-8:
                    continue
                trans, _ = self.tm.lookup(regime, from_cls, n_settle, n_forest)
                next_state += state[from_cls] * trans
            state = next_state

        state = np.maximum(state, PROB_FLOOR)
        state /= state.sum()
        return state

    def _empty_cell_prior(self, grid, y, x, h, w, regime):
        """Heuristic for empty cells (not in transition matrix).

        Uses settlement neighbor density from deep analysis expansion data.
        """
        n_settle, _ = self._count_neighbors(grid, y, x, h, w)

        dist = np.full(NUM_CLASSES, PROB_FLOOR)
        if regime == "growth" and n_settle >= 2:
            dist[0] = 0.50  # Empty
            dist[1] = 0.30  # Settlement
            dist[4] = 0.10  # Forest
        elif regime == "growth" and n_settle == 1:
            dist[0] = 0.65
            dist[1] = 0.15
            dist[4] = 0.10
        elif n_settle >= 2:
            dist[0] = 0.60
            dist[1] = 0.20
            dist[4] = 0.10
        else:
            dist[0] = 0.90
            dist[4] = 0.05

        dist = np.maximum(dist, PROB_FLOOR)
        dist /= dist.sum()
        return dist


def main():
    parser = argparse.ArgumentParser(description="Model C: CA-Markov")
    args = parser.parse_args()

    print("Loading cached rounds...")
    rounds_data = load_cached_rounds()
    print(f"  {len(rounds_data)} rounds loaded")

    print("\n=== Model C: CA-Markov Forward Simulation ===")
    results = evaluate_leave_one_out(ModelCCAMarkov, rounds_data)

    out_path = Path(__file__).parent / "data" / "eval_model_c.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
