"""
shared/stats.py -- Statistical utilities for experiment comparison.

Extracted from NM_I_AI_dash/tools/lib.py for reuse across tracks.

Usage:
    from shared.stats import compute_stats, welch_ttest

    stats_a = compute_stats([85, 87, 82, 90])
    stats_b = compute_stats([88, 91, 85, 93])
    comparison = welch_ttest([85, 87, 82, 90], [88, 91, 85, 93])
    print(comparison["verdict"])
"""

import numpy as np
from scipy import stats as scipy_stats


def compute_stats(scores: list) -> dict:
    """Compute summary statistics for a list of scores."""
    arr = np.array(scores, dtype=float)
    n = len(arr)
    return {
        "n": n,
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": round(float(arr.mean()), 4),
        "median": round(float(np.median(arr)), 4),
        "std": round(float(arr.std(ddof=1)) if n > 1 else 0.0, 4),
    }


def welch_ttest(scores_a: list, scores_b: list) -> dict:
    """
    Welch's t-test comparing two independent score distributions.

    Returns: {t_stat, p_value, effect_size_d, significant, winner, verdict}

    Use this to compare two approaches (A vs B) with statistical rigor
    instead of just eyeballing mean scores.
    """
    a = np.array(scores_a, dtype=float)
    b = np.array(scores_b, dtype=float)

    t_stat, p_value = scipy_stats.ttest_ind(a, b, equal_var=False)

    # Cohen's d effect size
    na, nb = len(a), len(b)
    pooled_var = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
    pooled_std = float(np.sqrt(pooled_var)) if pooled_var > 0 else 0.0
    effect_size_d = abs(float(b.mean() - a.mean())) / pooled_std if pooled_std > 0 else 0.0

    if effect_size_d < 0.2:
        magnitude = "negligible"
    elif effect_size_d < 0.5:
        magnitude = "small"
    elif effect_size_d < 0.8:
        magnitude = "medium"
    else:
        magnitude = "large"

    significant = bool(p_value < 0.05)
    winner = None
    if significant:
        winner = "B" if b.mean() > a.mean() else "A"
        verdict = f"Version {winner} wins (p={p_value:.3f}, d={effect_size_d:.2f}, {magnitude} effect)"
    else:
        verdict = f"No significant difference (p={p_value:.3f}, d={effect_size_d:.2f})"

    return {
        "t_stat": round(float(t_stat), 3),
        "p_value": round(float(p_value), 4),
        "effect_size_d": round(effect_size_d, 3),
        "significant": significant,
        "winner": winner,
        "verdict": verdict,
    }
