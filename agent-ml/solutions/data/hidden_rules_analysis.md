# Astar Island: Hidden Rules Analysis
**Analysis date:** 2026-03-20
**Data:** 7 rounds of ground truth (rounds 1-7), settlement stats for rounds 5-9
**Method:** Systematic analysis of initial grids vs ground truth probability tensors

---

## Executive Summary

The simulation has a small number of hidden parameters that control a Norse settlement growth/death game. The key findings:

A. The ground truth probabilities are generated from **200 Monte Carlo simulation runs** (probability granularity = 0.005 = 1/200).

B. There are distinct **round regimes** controlled by hidden parameters: death rounds (all settlements die), low-growth rounds, and high-growth rounds.

C. Settlement spread follows a **distance-dependent rule** from existing settlements: probability drops to zero beyond a round-dependent radius (3-8 Manhattan distance).

D. Forests are **consumed by expanding settlements** (adjacent forests get converted). Forests without adjacent settlements are near-100% stable.

E. Ports are **always coastal** (adjacent to ocean). Mountains and ocean never change.

---

## 1. Immutable Rules (constant across all rounds)

These rules hold in every single round observed:

| Rule | Confidence | Evidence |
|------|-----------|----------|
| Mountains never change | 100% | 100.0% stability in all 7 rounds |
| Ocean cells always map to Empty(0) in GT | 100% | 100.0% across all rounds |
| Ports require ocean adjacency | 100% | All 43 new ports across all rounds had at least 1 ocean neighbor |
| Empty cells never become forest (argmax) | 100% | 0/34,078 empty cells became forest in any round |
| Forests never become mountains | 100% | Never observed |
| Settlements never appear on mountains/ocean | 100% | Never observed |

---

## 2. Round Regimes

Rounds fall into 3-4 distinct parameter regimes:

### Regime A: Death Rounds (Rounds 3, 4)
- Settlement survival: **0-0.9%**
- Forest stability: **100%**
- New settlements: **0**
- S+P multiplier: **0.00-0.01x**
- Settlement probability (even on initial settlement cells): max ~8%
- Interpretation: extreme winter/apocalypse parameter. All civilization collapses.

### Regime B: Low-Growth / Stable Rounds (Rounds 1, 2)
- Settlement survival: **43-88%** (high variance across seeds)
- Forest stability: **98.8-99.7%**
- New settlements: **12-52**
- S+P multiplier: **0.67-0.82x** (net decline)
- Interpretation: mild conditions, settlements shrink slightly, forests stable.

### Regime C: Moderate Rounds (Round 5)
- Settlement survival: **~29%**
- Forest stability: **97.2%**
- New settlements: **87**
- S+P multiplier: **0.65x** (net decline despite expansion)
- Interpretation: expansion with high attrition.

### Regime D: High-Growth Rounds (Rounds 6, 7)
- Settlement survival: **41-72%**
- Forest stability: **83.7-90.2%**
- New settlements: **376-618**
- S+P multiplier: **2.15-2.86x** (massive net growth)
- Final settlement density: **7.3-11.1%** of land
- Interpretation: golden age, massive expansion, forests consumed.

### Key metrics per round:

| Round | Survival | Net S+P | Forest Stab | New S | New Ports | S+P Ratio |
|-------|----------|---------|-------------|-------|-----------|-----------|
| 1 | 58.7% | -37 | 98.8% | 52 | 3 | 0.82x |
| 2 | 63.3% | -80 | 99.7% | 12 | 2 | 0.67x |
| 3 | 0.0% | -215 | 100.0% | 0 | 0 | 0.00x |
| 4 | 0.9% | -237 | 100.0% | 0 | 0 | 0.01x |
| 5 | 29.3% | -85 | 97.2% | 87 | 1 | 0.65x |
| 6 | 57.7% | +275 | 90.2% | 376 | 8 | 2.15x |
| 7 | 61.3% | +505 | 83.7% | 618 | 29 | 2.86x |

---

## 3. Settlement Survival Rules

### 3A. Mountains kill settlements
Consistent signal across all non-death rounds:
- **0 adj mountains**: 59-63% survival (typical for the round)
- **2 adj mountains**: 14-37% survival (steep drop)
- **3+ adj mountains**: 0-20% survival

### 3B. Forests help (slightly)
More adjacent forests correlate with higher survival, but the effect is modest:
- **0 adj forests**: ~23-44% survival (lowest)
- **2-3 adj forests**: ~58-69% survival (typical)
- **5+ adj forests**: 62-100% survival (slight boost)

### 3C. Distance to other settlements matters
Survived settlements are **further** from the nearest other settlement than dead ones:
- Survived mean distance: 4.5-5.1
- Died mean distance: 3.7-4.3
- This suggests **competition/conflict** between nearby settlements.

### 3D. Edge vs center
Slight edge advantage in some rounds (67-72% edge vs 50-58% center in rounds 1, 2, 6), but not consistent. Round 7 shows no difference (61.5% vs 61.2%).

### 3E. No same-faction adjacency in initial grid
Initial settlements NEVER have adjacent settlements (adj_settlement = 0 for all initial settlements across all rounds). The initial grid generator spaces settlements apart.

---

## 4. Settlement Growth Patterns

### 4A. Distance-dependent spread
The most critical finding for prediction. Settlement probability on non-settlement cells drops sharply with Manhattan distance from the nearest initial settlement:

**Round 7 (sharpest cutoff):**
| Manhattan dist | Mean S+P prob | Max prob |
|---------------|--------------|---------|
| 1 | 0.382 | 0.795 |
| 2 | 0.254 | 0.715 |
| 3 | 0.121 | 0.585 |
| 4 | **0.001** | 0.040 |
| 5+ | **0.000** | 0.000 |

**Round 1 (wider spread):**
| Manhattan dist | Mean S+P prob | Max prob |
|---------------|--------------|---------|
| 1 | 0.245 | 0.590 |
| 4 | 0.191 | 0.470 |
| 8 | 0.028 | 0.135 |
| 9 | 0.003 | 0.025 |
| 11+ | ~0.000 | 0.010 |

**Round 6 (widest spread):**
| Manhattan dist | Mean S+P prob | Max prob |
|---------------|--------------|---------|
| 1 | 0.314 | 0.645 |
| 8 | 0.133 | 0.370 |
| 10 | 0.061 | 0.130 |
| 12 | 0.020 | 0.040 |

The "spread radius" varies by round: ~8-10 in rounds 1-2, ~6-7 in round 5, 3 in round 7, >12 in round 6.

### 4B. Source terrain for new settlements
New settlements can appear on both empty and forest cells. Forest is NOT required.
- Round 6: 44% on forest, 56% on empty
- Round 7: 40% on forest, 60% on empty

### 4C. Adjacency to existing settlements
In high-growth rounds, 45-92% of new settlements are adjacent (dist=1) to an existing settlement. In round 7, this is 92.4%, suggesting spread is primarily neighbor-to-neighbor.

### 4D. Forest adjacency effect on new settlement probability
Surprisingly, forest adjacency does NOT significantly increase settlement probability for a given cell. The effect is weak (mean S+P prob varies only ~0.18-0.25 regardless of forest count). The main driver is distance to existing settlements.

---

## 5. Forest Dynamics

### 5A. Forests are consumed by settlements
Forest cells adjacent to settlements have much lower survival rates in growth rounds:
- **Round 7, 0 adj settlements**: 97-99% forest survival
- **Round 7, 1 adj settlement**: 50-60% forest survival
- **Round 7, 2 adj settlements**: 36-60% forest survival

Forest-to-settlement conversion is THE mechanism for settlement expansion.

### 5B. Isolated forests are nearly immortal
Forest cells with no adjacent settlements: 92-99% survival in all non-death rounds. Forest count of adjacent forests does not affect survival.

### 5C. No new forests appear
In ALL 7 rounds, zero empty cells became forest (argmax). Forests can only shrink, never grow. This is a one-way process.

### 5D. Dead settlements partly return to forest
When settlements die, they get significant forest probability:
- Dead settlement mean forest probability: 19-30% (highest in death rounds: 30%)
- Dead settlement mean empty probability: 44-68%
- This represents the stochastic nature: in some simulation runs the land regrows forest, in others it stays empty.

---

## 6. Port Mechanics

### 6A. Ports are always coastal
100% of new ports (43 across all rounds) were adjacent to at least 1 ocean cell. Average 2-3 ocean neighbors.

### 6B. Port survival is very low
Across all rounds: 8/70 initial ports survived (11.4%). Ports are unstable.

### 6C. Port probability is always small
Even for initial port cells, port probability is low (12-32% on average). The simulation seems to treat port as a rare secondary outcome for coastal settlements.

### 6D. New ports scale with growth
- Death rounds: 0 new ports
- Low-growth: 2-3 new ports
- High-growth: 8-29 new ports

---

## 7. Ruin Mechanics

### 7A. Ruin is never the argmax
In ALL 7 rounds across all cells, ruin probability NEVER exceeds ~10%. No cell has ruin as the most likely outcome.

### 7B. Ruin probability exists everywhere
Ruin probability (>1%) appears on 23-6239 cells per round. It's most common in high-growth rounds (round 6: 6239 cells). Sources include empty, forest, and settlement cells.

### 7C. Ruin is a "background" probability
Mean ruin probability on settlement cells: 2-4%. Ruin appears to be a low-probability stochastic outcome in the Monte Carlo simulation (e.g., a settlement that died and left ruins in some simulation runs).

---

## 8. Probability Structure

### 8A. Monte Carlo simulation with 200 runs
All probabilities are multiples of 0.005 (1/200). The simulator runs the 50-year evolution 200 times and counts outcomes per cell. This is the ground truth.

### 8B. Uncertainty varies by round
| Round | Mean max_prob | Uncertain cells (max<0.8) |
|-------|--------------|--------------------------|
| 1 | 0.765 | 62.1% |
| 2 | 0.703 | 87.1% |
| 3 | 0.973 | 4.7% |
| 4 | 0.834 | 28.3% |
| 5 | 0.798 | 42.9% |
| 6 | 0.619 | 93.7% |
| 7 | 0.813 | 40.1% |

Death rounds have high certainty (everything becomes empty). High-growth rounds have high uncertainty (many possible outcomes per cell).

### 8C. Cross-seed consistency
Within a round, settlement survival rates vary by 5-13% standard deviation across seeds. The hidden parameters affect all seeds the same way, but the specific map layout creates variance.

---

## 9. Faction Structure (from settlement stats, rounds 5-9)

### 9A. 20-28 factions per round
Each round has approximately 21-28 unique owner_ids among alive settlements.

### 9B. Faction territories are contiguous
Faction territories show high contiguity (128-212% of settlements have same-faction neighbors, meaning most have multiple). Factions form territorial blobs.

### 9C. Largest faction controls 15-25% of settlements
Top faction sizes: 18-54 settlements out of 51-356 total. Max territory span: 6-16 Manhattan distance.

### 9D. Port settlements have higher stats
Ports consistently show higher population and defense than non-ports:
- Port defense: 0.18-0.75 mean
- Non-port defense: 0.29-0.55 mean
- Port population: 0.74-1.97 vs non-port 0.97-1.25

---

## 10. Key Modeling Implications

### For prediction, the most impactful rules:

1. **Distance-based settlement probability**: Settlement probability should decay with distance from existing settlements. The radius varies per round (hidden parameter). Modeling this correctly would dramatically improve settlement class KL divergence.

2. **Death round detection**: If observations show all settlements dying, apply the death-round template (everything non-forest/mountain -> empty with high probability). Round 3/4 pattern.

3. **Forest consumption**: Forests adjacent to settlements get consumed. Forest survival probability should decrease with adjacent settlement count. This is mechanistic, not just correlational.

4. **Ocean cells = Empty**: Trivial but worth 100% of ocean cell entropy. Always predict [1,0,0,0,0,0].

5. **Mountains = Mountain**: Always predict [0,0,0,0,0,1]. Already solved.

6. **Port = coastal + rare**: Port probability should only be nonzero on cells adjacent to ocean. Even then, it's small (5-30% max on ideal cells).

7. **Ruin = background noise**: Always include 2-4% ruin probability on cells that could potentially be settlement/empty. Never predict ruin as argmax.

8. **Forest = base probability**: All non-ocean, non-mountain cells have 3-30% forest probability. This reflects the stochastic possibility of forest reclamation after settlement collapse.

### What we still don't know:
- The exact mapping from hidden parameters to survival/growth rates
- Whether owner_id/faction data from observations can predict which specific settlements survive
- How the simulation determines which settlements compete (faction-based warfare?)
- Whether there are year-by-year dynamics we could exploit with observation timing

---

## 11. Recommended Model Architecture

Based on these findings, the ideal prediction model should:

A. **Classify the round regime** from early observations (death/low/moderate/high growth)
B. **Compute distance maps** from initial settlement positions
C. **Apply distance-dependent settlement probability** scaled by the detected regime
D. **Reduce forest probability** proportional to adjacent settlements (in growth rounds)
E. **Restrict port probability** to ocean-adjacent cells only
F. **Include ruin as background** noise (2-5% on non-static cells)
G. **Floor all probabilities** at 0.005-0.01 and renormalize (the 200-run MC guarantees some variance)
