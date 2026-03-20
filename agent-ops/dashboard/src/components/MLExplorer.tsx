import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { getTile, TILE_SOURCE_SIZE } from "../canvas/terrainTiles";
import { TERRAIN_COLORS, GRID_COLORS } from "../canvas/terrainColors";
import { TERRAIN_NAMES, TERRAIN_TO_CLASS } from "../types/dashboard";

// ─── Types ─────────────────────────────────────────────────────────────────────

type ViewMode = "initial" | "ground_truth" | "prediction" | "diff" | "kl_heatmap";

interface MLTerrainSeed {
  initial_grid: number[][];
  ground_truth: number[][][] | null;
  our_prediction: number[][][] | null;
}

interface MLTerrainRound {
  round_number: number;
  status: string;
  seeds: MLTerrainSeed[];
}

interface MLTerrainData {
  rounds: Record<string, MLTerrainRound>;
  last_fetched: string;
}

interface MLRoundEntry {
  round_id: string;
  round_number: number;
  status: string;
  opens_at: string;
  closes_at: string;
  round_weight: number;
  our_score: number | null;
  seed_scores: number[] | null;
  our_rank: number | null;
  total_teams: number | null;
  seeds_submitted: number;
  queries_used: number;
  queries_total: number;
}

interface MLRoundsData {
  rounds: MLRoundEntry[];
  active_round: {
    round_id: string;
    round_number: number;
    closes_at: string;
    budget_remaining: number;
  } | null;
  last_fetched: string;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const GRID_SIZE = 40;
const COORD_MARGIN = 24;
const CLASS_NAMES = ["Empty", "Settlement", "Port", "Ruin", "Forest", "Mountain"] as const;
const CLASS_COLORS = ["#c4a882", "#8b6914", "#1a4b8c", "#5a5a5a", "#1a5c2a", "#6a6a6a"] as const;

// ─── Utility functions ─────────────────────────────────────────────────────────

function probToArgmax(probs: number[]): number {
  let maxIdx = 0;
  let maxVal = probs[0] ?? 0;
  for (let i = 1; i < probs.length; i++) {
    const v = probs[i] ?? 0;
    if (v > maxVal) {
      maxVal = v;
      maxIdx = i;
    }
  }
  return maxIdx;
}

/** KL divergence for a single cell: D_KL(truth || pred) */
function klDivergence(truth: number[], pred: number[]): number {
  let kl = 0;
  for (let i = 0; i < truth.length; i++) {
    const p = truth[i] ?? 0;
    const q = Math.max(pred[i] ?? 0.01, 0.001);
    if (p > 0) {
      kl += p * Math.log(p / q);
    }
  }
  return kl;
}

/** Generate animation thresholds per cell */
function generateThresholds(h: number, w: number): number[][] {
  const out: number[][] = [];
  for (let y = 0; y < h; y++) {
    const row: number[] = [];
    for (let x = 0; x < w; x++) {
      const hash = Math.sin(y * 127.1 + x * 311.7) * 43758.5453;
      row.push((hash - Math.floor(hash)) * 0.85 + 0.05);
    }
    out.push(row);
  }
  return out;
}

/** Count terrain types in a grid */
function countTerrain(grid: number[][]): Map<number, number> {
  const counts = new Map<number, number>();
  for (const row of grid) {
    for (const val of row) {
      counts.set(val, (counts.get(val) ?? 0) + 1);
    }
  }
  return counts;
}

// ─── Terrain Legend with counts (dark theme) ────────────────────────────────

interface LegendEntry {
  code: number;
  name: string;
  color: string;
  count: number;
}

function DarkTerrainLegend({ entries }: { entries: LegendEntry[] }) {
  const total = entries.reduce((s, e) => s + e.count, 0);
  return (
    <div className="space-y-1">
      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
        Terrain Legend
      </h4>
      {entries.map((e) => (
        <div key={e.code} className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-sm border border-white/20 flex-shrink-0"
            style={{ backgroundColor: e.color }}
          />
          <span className="text-xs text-slate-300 flex-1 truncate">{e.name}</span>
          <span className="text-xs text-slate-500 tabular-nums">
            {e.count}
          </span>
          <span className="text-[10px] text-slate-600 tabular-nums w-10 text-right">
            {total > 0 ? `${((e.count / total) * 100).toFixed(0)}%` : "0%"}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Score sparkline (inline SVG) ──────────────────────────────────────────

function ScoreSparkline({ scores }: { scores: { round: number; score: number }[] }) {
  if (scores.length === 0) return null;
  const w = 200;
  const h = 48;
  const padX = 4;
  const padY = 4;
  const min = Math.min(...scores.map((s) => s.score));
  const max = Math.max(...scores.map((s) => s.score));
  const range = max - min || 1;

  const points = scores.map((s, i) => {
    const x = padX + (i / Math.max(scores.length - 1, 1)) * (w - padX * 2);
    const y = padY + (1 - (s.score - min) / range) * (h - padY * 2);
    return { x, y, score: s.score, round: s.round };
  });

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  return (
    <div>
      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
        Score History
      </h4>
      <svg width={w} height={h} className="block">
        {/* Grid lines */}
        <line x1={padX} y1={h - padY} x2={w - padX} y2={h - padY} stroke="#334155" strokeWidth={0.5} />
        <line x1={padX} y1={padY} x2={w - padX} y2={padY} stroke="#334155" strokeWidth={0.5} />
        {/* Score line */}
        <path d={pathD} fill="none" stroke="#38bdf8" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        {/* Dots */}
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={3} fill="#0ea5e9" stroke="#0c4a6e" strokeWidth={1}>
            <title>R{p.round}: {p.score.toFixed(1)}</title>
          </circle>
        ))}
        {/* Min/Max labels */}
        <text x={w - padX} y={padY - 1} textAnchor="end" fill="#64748b" fontSize={8}>
          {max.toFixed(0)}
        </text>
        <text x={w - padX} y={h - 1} textAnchor="end" fill="#64748b" fontSize={8}>
          {min.toFixed(0)}
        </text>
      </svg>
    </div>
  );
}

// ─── Distribution bars (horizontal) ────────────────────────────────────────

function DistributionBars({ counts }: { counts: Map<number, number> }) {
  const maxCount = Math.max(...Array.from(counts.values()), 1);
  return (
    <div>
      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
        Terrain Distribution
      </h4>
      <div className="space-y-1">
        {CLASS_NAMES.map((name, i) => {
          const count = counts.get(i) ?? 0;
          const pct = (count / maxCount) * 100;
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400 w-16 truncate">{name}</span>
              <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{ width: `${pct}%`, backgroundColor: CLASS_COLORS[i] }}
                />
              </div>
              <span className="text-[10px] text-slate-500 tabular-nums w-8 text-right">{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Probability tooltip bars ──────────────────────────────────────────────

function ProbBars({ probs }: { probs: number[] }) {
  return (
    <div className="space-y-0.5">
      {CLASS_NAMES.map((name, i) => {
        const p = probs[i] ?? 0;
        return (
          <div key={i} className="flex items-center gap-1">
            <span className="text-[9px] text-slate-300 w-12 truncate">{name}</span>
            <div className="w-16 h-1.5 bg-slate-600 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${p * 100}%`, backgroundColor: CLASS_COLORS[i] }}
              />
            </div>
            <span className="text-[9px] text-slate-400 tabular-nums w-8">
              {(p * 100).toFixed(0)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main MLExplorer Component ─────────────────────────────────────────────

export function MLExplorer() {
  // --- Data state ---
  const [terrainData, setTerrainData] = useState<MLTerrainData | null>(null);
  const [roundsData, setRoundsData] = useState<MLRoundsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // --- UI state ---
  const [selectedRound, setSelectedRound] = useState<string>("round_7");
  const [selectedSeed, setSelectedSeed] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("initial");
  const [cellSize, setCellSize] = useState(16);
  const [tooltipData, setTooltipData] = useState<{
    x: number;
    y: number;
    screenX: number;
    screenY: number;
    terrain: number;
    terrainName: string;
    gtProbs: number[] | null;
    predProbs: number[] | null;
  } | null>(null);

  // --- Animation state ---
  const [animProgress, setAnimProgress] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const animRef = useRef(0);
  const progressRef = useRef(0);
  const thresholds = useMemo(() => generateThresholds(GRID_SIZE, GRID_SIZE), []);

  // --- Canvas refs ---
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // --- Load data ---
  useEffect(() => {
    const loadData = async () => {
      try {
        const [terrainResp, roundsResp] = await Promise.all([
          fetch("/data/ml_terrain.json"),
          fetch("/data/ml_rounds.json"),
        ]);
        if (!terrainResp.ok) throw new Error(`Terrain data: HTTP ${terrainResp.status}`);
        if (!roundsResp.ok) throw new Error(`Rounds data: HTTP ${roundsResp.status}`);
        const terrain = (await terrainResp.json()) as MLTerrainData;
        const rounds = (await roundsResp.json()) as MLRoundsData;
        setTerrainData(terrain);
        setRoundsData(rounds);

        // Auto-select latest round with ground truth
        const roundKeys = Object.keys(terrain.rounds).sort(
          (a, b) => (terrain.rounds[b]?.round_number ?? 0) - (terrain.rounds[a]?.round_number ?? 0)
        );
        for (const key of roundKeys) {
          const rd = terrain.rounds[key];
          if (rd && rd.seeds.some((s) => s.ground_truth !== null)) {
            setSelectedRound(key);
            break;
          }
        }
      } catch (e) {
        setError(String(e));
      }
    };
    void loadData();
    const interval = setInterval(() => void loadData(), 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // --- Derived data ---
  const currentRound = terrainData?.rounds[selectedRound] ?? null;
  const currentSeed = currentRound?.seeds[selectedSeed] ?? null;
  const roundNumber = currentRound?.round_number ?? 0;

  // Find round info from ml_rounds.json
  const roundInfo = useMemo(() => {
    if (!roundsData) return null;
    return roundsData.rounds.find((r) => r.round_number === roundNumber) ?? null;
  }, [roundsData, roundNumber]);

  // Available round keys sorted by round number
  const sortedRoundKeys = useMemo(() => {
    if (!terrainData) return [];
    return Object.keys(terrainData.rounds).sort(
      (a, b) =>
        (terrainData.rounds[a]?.round_number ?? 0) - (terrainData.rounds[b]?.round_number ?? 0)
    );
  }, [terrainData]);

  // Score history for sparkline
  const scoreHistory = useMemo(() => {
    if (!roundsData) return [];
    return roundsData.rounds
      .filter((r) => r.our_score !== null)
      .sort((a, b) => a.round_number - b.round_number)
      .map((r) => ({ round: r.round_number, score: r.our_score! }));
  }, [roundsData]);

  // Compute display grid based on view mode
  const { displayGrid, klGrid } = useMemo(() => {
    if (!currentSeed) return { displayGrid: [] as number[][], klGrid: null };

    const initial = currentSeed.initial_grid;
    const gt = currentSeed.ground_truth;
    const pred = currentSeed.our_prediction;

    switch (viewMode) {
      case "initial":
        return { displayGrid: initial, klGrid: null };

      case "ground_truth": {
        if (!gt) return { displayGrid: initial, klGrid: null };
        const grid = gt.map((row) => row.map(probToArgmax));
        return { displayGrid: grid, klGrid: null };
      }

      case "prediction": {
        if (!pred) return { displayGrid: initial, klGrid: null };
        const grid = pred.map((row) => row.map(probToArgmax));
        return { displayGrid: grid, klGrid: null };
      }

      case "diff": {
        if (!gt || !pred) return { displayGrid: initial, klGrid: null };
        // -1 = correct, -2 = wrong, terrain code for display
        const gtGrid = gt.map((row) => row.map(probToArgmax));
        const predGrid = pred.map((row) => row.map(probToArgmax));
        const diffGrid = gtGrid.map((row, y) =>
          row.map((gtTerrain, x) => {
            const predTerrain = predGrid[y]?.[x] ?? 0;
            return gtTerrain === predTerrain ? -1 : -2;
          })
        );
        return { displayGrid: diffGrid, klGrid: null };
      }

      case "kl_heatmap": {
        if (!gt || !pred) return { displayGrid: initial, klGrid: null };
        const kl = gt.map((row, y) =>
          row.map((gtProbs, x) => {
            const predProbs = pred[y]?.[x] ?? [1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6, 1 / 6];
            return klDivergence(gtProbs, predProbs);
          })
        );
        // Display the prediction argmax grid underneath
        const baseGrid = pred.map((row) => row.map(probToArgmax));
        return { displayGrid: baseGrid, klGrid: kl };
      }

      default:
        return { displayGrid: initial, klGrid: null };
    }
  }, [currentSeed, viewMode]);

  // Animated grid for playback
  const animatedGrid = useMemo(() => {
    if (!isPlaying && animProgress === 0) return null;
    if (!currentSeed?.initial_grid || !currentSeed?.ground_truth) return null;
    const initial = currentSeed.initial_grid;
    const gt = currentSeed.ground_truth;
    return initial.map((row, y) =>
      row.map((initTerrain, x) => {
        const probs = gt[y]?.[x];
        if (!probs) return initTerrain;
        const finalTerrain = probToArgmax(probs);
        const initClass = TERRAIN_TO_CLASS[initTerrain] ?? 0;
        if (initClass === finalTerrain) return initTerrain;
        return animProgress >= (thresholds[y]?.[x] ?? 0.5) ? finalTerrain : initTerrain;
      })
    );
  }, [currentSeed, animProgress, isPlaying, thresholds]);

  // Terrain counts for the displayed grid
  const terrainCounts = useMemo(() => {
    const grid = animatedGrid ?? displayGrid;
    if (grid.length === 0) return new Map<number, number>();
    return countTerrain(grid);
  }, [displayGrid, animatedGrid]);

  // Legend entries
  const legendEntries = useMemo((): LegendEntry[] => {
    const isDiff = viewMode === "diff" && !isPlaying;
    if (isDiff) {
      return [
        { code: -1, name: "Correct", color: "#22c55e", count: terrainCounts.get(-1) ?? 0 },
        { code: -2, name: "Wrong", color: "#ef4444", count: terrainCounts.get(-2) ?? 0 },
      ];
    }
    const items: LegendEntry[] = [];
    const terrainEntries: [number, string][] = [
      [0, "Empty"],
      [1, "Settlement"],
      [2, "Port"],
      [3, "Ruin"],
      [4, "Forest"],
      [5, "Mountain"],
      [10, "Ocean"],
      [11, "Plains"],
    ];
    for (const [code, name] of terrainEntries) {
      const count = terrainCounts.get(code) ?? 0;
      if (count > 0) {
        items.push({ code, name, color: TERRAIN_COLORS[code] ?? "#666", count });
      }
    }
    return items;
  }, [viewMode, terrainCounts, isPlaying]);

  // Coverage stats (how many cells have prediction data)
  const coverage = useMemo(() => {
    if (!currentSeed?.our_prediction) return { observed: 0, total: GRID_SIZE * GRID_SIZE };
    // Count cells where prediction is not uniform (i.e., we actually predicted something)
    let observed = 0;
    for (const row of currentSeed.our_prediction) {
      for (const probs of row) {
        const max = Math.max(...probs);
        if (max > 0.5) observed++;
      }
    }
    return { observed, total: GRID_SIZE * GRID_SIZE };
  }, [currentSeed]);

  // Diff accuracy stats
  const diffStats = useMemo(() => {
    if (viewMode !== "diff" || !currentSeed?.ground_truth || !currentSeed?.our_prediction) {
      return null;
    }
    const gt = currentSeed.ground_truth;
    const pred = currentSeed.our_prediction;
    let correct = 0;
    let total = 0;
    for (let y = 0; y < GRID_SIZE; y++) {
      for (let x = 0; x < GRID_SIZE; x++) {
        const gtProbs = gt[y]?.[x];
        const predProbs = pred[y]?.[x];
        if (!gtProbs || !predProbs) continue;
        total++;
        if (probToArgmax(gtProbs) === probToArgmax(predProbs)) correct++;
      }
    }
    return { correct, total, accuracy: total > 0 ? (correct / total) * 100 : 0 };
  }, [viewMode, currentSeed]);

  // --- Canvas rendering (getTile() lazily inits cache) ---

  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const grid = animatedGrid ?? displayGrid;
    if (grid.length === 0) return;

    const isDiff = viewMode === "diff" && !isPlaying;
    const isKL = viewMode === "kl_heatmap" && !isPlaying;

    const totalW = COORD_MARGIN + GRID_SIZE * cellSize;
    const totalH = COORD_MARGIN + GRID_SIZE * cellSize;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = totalW * dpr;
    canvas.height = totalH * dpr;
    canvas.style.width = `${totalW}px`;
    canvas.style.height = `${totalH}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Background
    ctx.fillStyle = GRID_COLORS.background;
    ctx.fillRect(0, 0, totalW, totalH);

    ctx.save();
    ctx.translate(COORD_MARGIN, COORD_MARGIN);

    // Draw cells
    for (let y = 0; y < GRID_SIZE; y++) {
      const row = grid[y];
      if (!row) continue;
      for (let x = 0; x < GRID_SIZE; x++) {
        const terrain = row[x];
        if (terrain === undefined) continue;
        const px = x * cellSize;
        const py = y * cellSize;

        if (isDiff) {
          // Diff mode: green = correct, red = wrong
          if (terrain === -1) {
            ctx.fillStyle = "rgba(34, 197, 94, 0.4)";
            ctx.fillRect(px, py, cellSize, cellSize);
            // Draw the actual GT terrain faintly
            const gtTerrain = currentSeed?.ground_truth?.[y]?.[x];
            if (gtTerrain) {
              const tile = getTile(probToArgmax(gtTerrain));
              ctx.globalAlpha = 0.5;
              ctx.drawImage(tile, 0, 0, TILE_SOURCE_SIZE, TILE_SOURCE_SIZE, px, py, cellSize, cellSize);
              ctx.globalAlpha = 1;
            }
          } else if (terrain === -2) {
            ctx.fillStyle = "rgba(239, 68, 68, 0.4)";
            ctx.fillRect(px, py, cellSize, cellSize);
            const gtTerrain = currentSeed?.ground_truth?.[y]?.[x];
            if (gtTerrain) {
              const tile = getTile(probToArgmax(gtTerrain));
              ctx.globalAlpha = 0.5;
              ctx.drawImage(tile, 0, 0, TILE_SOURCE_SIZE, TILE_SOURCE_SIZE, px, py, cellSize, cellSize);
              ctx.globalAlpha = 1;
            }
            // Red X overlay for wrong cells
            if (cellSize >= 12) {
              ctx.strokeStyle = "rgba(239, 68, 68, 0.8)";
              ctx.lineWidth = 1;
              ctx.beginPath();
              ctx.moveTo(px + 2, py + 2);
              ctx.lineTo(px + cellSize - 2, py + cellSize - 2);
              ctx.moveTo(px + cellSize - 2, py + 2);
              ctx.lineTo(px + 2, py + cellSize - 2);
              ctx.stroke();
            }
          }
        } else {
          // Normal terrain rendering
          const tile = getTile(terrain);
          ctx.drawImage(tile, 0, 0, TILE_SOURCE_SIZE, TILE_SOURCE_SIZE, px, py, cellSize, cellSize);
        }

        // KL heatmap overlay
        if (isKL && klGrid) {
          const kl = klGrid[y]?.[x] ?? 0;
          // Map KL to color: 0 = green (good), high = red (bad)
          // Typical KL range: 0 to ~3
          const t = Math.min(kl / 2, 1);
          const r = Math.round(t * 255);
          const g = Math.round((1 - t) * 200);
          ctx.fillStyle = `rgba(${r}, ${g}, 0, 0.55)`;
          ctx.fillRect(px, py, cellSize, cellSize);
        }

        // Grid lines
        ctx.strokeStyle = GRID_COLORS.gridLine;
        ctx.lineWidth = 0.5;
        ctx.strokeRect(px, py, cellSize, cellSize);
      }
    }

    // Coordinate labels
    ctx.fillStyle = GRID_COLORS.coordLabel;
    ctx.font = `${Math.max(7, Math.min(10, cellSize * 0.6))}px monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    const labelStep = cellSize >= 12 ? 5 : 10;

    for (let x = 0; x < GRID_SIZE; x += labelStep) {
      ctx.fillText(String(x), x * cellSize + cellSize / 2, -COORD_MARGIN / 2);
    }
    ctx.textAlign = "right";
    for (let y = 0; y < GRID_SIZE; y += labelStep) {
      ctx.fillText(String(y), -COORD_MARGIN / 4, y * cellSize + cellSize / 2);
    }

    ctx.restore();
  }, [displayGrid, animatedGrid, viewMode, cellSize, klGrid, isPlaying, currentSeed]);

  // Render when data changes
  useEffect(() => {
    renderCanvas();
  }, [renderCanvas]);

  // --- Animation ---
  const animate = useCallback(() => {
    progressRef.current += 0.008;
    if (progressRef.current >= 1) {
      progressRef.current = 1;
      setAnimProgress(1);
      setIsPlaying(false);
      return;
    }
    setAnimProgress(progressRef.current);
    animRef.current = requestAnimationFrame(animate);
  }, []);

  const startAnimation = useCallback(() => {
    progressRef.current = 0;
    setAnimProgress(0);
    setIsPlaying(true);
    animRef.current = requestAnimationFrame(animate);
  }, [animate]);

  useEffect(() => () => cancelAnimationFrame(animRef.current), []);

  // --- Mouse hover for tooltip ---
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas || !currentSeed) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const gx = Math.floor((mx - COORD_MARGIN) / cellSize);
      const gy = Math.floor((my - COORD_MARGIN) / cellSize);

      if (gx >= 0 && gx < GRID_SIZE && gy >= 0 && gy < GRID_SIZE) {
        const terrain = currentSeed.initial_grid[gy]?.[gx] ?? 0;
        const terrainName = TERRAIN_NAMES[terrain] ?? "Unknown";
        const gtProbs = currentSeed.ground_truth?.[gy]?.[gx] ?? null;
        const predProbs = currentSeed.our_prediction?.[gy]?.[gx] ?? null;
        setTooltipData({
          x: gx,
          y: gy,
          screenX: e.clientX,
          screenY: e.clientY,
          terrain,
          terrainName,
          gtProbs,
          predProbs,
        });
      } else {
        setTooltipData(null);
      }
    },
    [currentSeed, cellSize],
  );

  const handleMouseLeave = useCallback(() => {
    setTooltipData(null);
  }, []);

  // --- Seed score for the selected round ---
  const seedScores = useMemo(() => {
    if (!roundsData) return null;
    const ri = roundsData.rounds.find((r) => r.round_number === roundNumber);
    return ri?.seed_scores ?? null;
  }, [roundsData, roundNumber]);

  // --- Has ground truth / prediction ---
  const hasGT = currentSeed?.ground_truth !== null;
  const hasPred = currentSeed?.our_prediction !== null;
  const hasData = hasGT || hasPred;

  // --- View mode button config ---
  const viewModes: { mode: ViewMode; label: string; needsGT: boolean; needsPred: boolean }[] = [
    { mode: "initial", label: "Initial", needsGT: false, needsPred: false },
    { mode: "ground_truth", label: "Ground Truth", needsGT: true, needsPred: false },
    { mode: "prediction", label: "Our Prediction", needsGT: false, needsPred: true },
    { mode: "diff", label: "Diff", needsGT: true, needsPred: true },
    { mode: "kl_heatmap", label: "KL Heatmap", needsGT: true, needsPred: true },
  ];

  // --- KL summary stats for heatmap mode ---
  const klStats = useMemo(() => {
    if (!klGrid) return null;
    let sum = 0;
    let max = 0;
    let count = 0;
    for (const row of klGrid) {
      for (const val of row) {
        sum += val;
        if (val > max) max = val;
        count++;
      }
    }
    return { mean: count > 0 ? sum / count : 0, max, total: sum };
  }, [klGrid]);

  // ─── Error / Loading states ──────────────────────────────────────────────

  if (error) {
    return (
      <div className="flex-1 p-6">
        <div className="rounded-2xl bg-red-50/80 border border-red-200 p-6">
          <h3 className="text-lg font-bold text-red-800 font-[Fredoka]">Data Load Error</h3>
          <p className="text-sm text-red-600 mt-2">{error}</p>
        </div>
      </div>
    );
  }

  if (!terrainData || !roundsData) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sky-500 animate-pulse font-[Fredoka]">Loading terrain data...</p>
      </div>
    );
  }

  // ─── Render ──────────────────────────────────────────────────────────────

  let yearDisplay = 0;
  if (isPlaying) {
    yearDisplay = Math.round(animProgress * 50);
  } else if (viewMode === "ground_truth") {
    yearDisplay = 50;
  }

  return (
    <div className="flex-1 flex overflow-hidden h-full">
      {/* ═══════════════ LEFT PANEL: Terrain Grid ═══════════════ */}
      <div className="flex-[3] flex flex-col min-w-0 p-4 gap-3">
        {/* Header row */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h2 className="text-xl font-bold text-sky-800 font-[Fredoka]">
              ML Explorer
            </h2>
            <p className="text-xs text-sky-500">
              Astar Island terrain prediction, 40x40 grid, 6 terrain classes
            </p>
          </div>
          {hasGT && (
            <button
              onClick={startAnimation}
              disabled={isPlaying}
              className={`px-4 py-2 rounded-full text-sm font-bold transition-all ${
                isPlaying
                  ? "bg-sky-600 text-white animate-pulse"
                  : "bg-sky-800 text-white hover:bg-sky-700 shadow-md"
              }`}
            >
              {isPlaying ? `Year ${yearDisplay}...` : "Play 50-Year Simulation"}
            </button>
          )}
        </div>

        {/* View mode buttons */}
        <div className="flex gap-2 items-center flex-wrap">
          <span className="text-xs text-sky-600 font-semibold">View:</span>
          {viewModes.map(({ mode, label, needsGT, needsPred }) => {
            const enabled = (!needsGT || hasGT) && (!needsPred || hasPred);
            const isActive = viewMode === mode && !isPlaying;
            let btnStyle = "bg-white/30 text-sky-400 cursor-not-allowed";
            if (isActive) {
              btnStyle = "bg-sky-800 text-white shadow-md";
            } else if (enabled) {
              btnStyle = "bg-white/60 text-sky-700 hover:bg-white/80";
            }
            return (
              <button
                key={mode}
                onClick={() => {
                  setViewMode(mode);
                  setIsPlaying(false);
                  cancelAnimationFrame(animRef.current);
                  setAnimProgress(0);
                }}
                disabled={!enabled}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${btnStyle}`}
              >
                {label}
              </button>
            );
          })}

          {/* Animation progress */}
          {isPlaying && (
            <div className="flex items-center gap-2 ml-2 flex-1 max-w-xs">
              <span className="text-[10px] text-sky-500">Y0</span>
              <div className="flex-1 h-2 bg-white/30 rounded-full overflow-hidden">
                <div
                  className="h-full bg-sky-600 rounded-full transition-[width] duration-100"
                  style={{ width: `${animProgress * 100}%` }}
                />
              </div>
              <span className="text-[10px] text-sky-500">Y50</span>
            </div>
          )}
        </div>

        {/* Zoom slider */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-sky-600 font-semibold">Zoom:</span>
          <input
            type="range"
            min={8}
            max={32}
            value={cellSize}
            onChange={(e) => setCellSize(Number(e.target.value))}
            className="w-32 accent-sky-600"
          />
          <span className="text-xs text-sky-500 tabular-nums">{cellSize}px</span>
        </div>

        {/* Diff stats banner */}
        {viewMode === "diff" && diffStats && !isPlaying && (
          <div className="flex gap-3 text-xs">
            <span className="px-3 py-1 rounded-full bg-green-100 text-green-800 font-semibold">
              Correct: {diffStats.correct}/{diffStats.total}
            </span>
            <span className="px-3 py-1 rounded-full bg-red-100 text-red-800 font-semibold">
              Wrong: {diffStats.total - diffStats.correct}/{diffStats.total}
            </span>
            <span className="px-3 py-1 rounded-full bg-sky-100 text-sky-800 font-semibold">
              Accuracy: {diffStats.accuracy.toFixed(1)}%
            </span>
          </div>
        )}

        {/* KL stats banner */}
        {viewMode === "kl_heatmap" && klStats && !isPlaying && (
          <div className="flex gap-3 text-xs flex-wrap">
            <span className="px-3 py-1 rounded-full bg-amber-100 text-amber-800 font-semibold">
              Mean KL: {klStats.mean.toFixed(4)}
            </span>
            <span className="px-3 py-1 rounded-full bg-red-100 text-red-800 font-semibold">
              Max KL: {klStats.max.toFixed(4)}
            </span>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-sm" style={{ background: "rgba(0,200,0,0.55)" }} />
              <span className="text-sky-600">Good</span>
              <div className="w-12 h-2 rounded-full" style={{
                background: "linear-gradient(to right, rgba(0,200,0,0.55), rgba(255,0,0,0.55))"
              }} />
              <div className="w-3 h-3 rounded-sm" style={{ background: "rgba(255,0,0,0.55)" }} />
              <span className="text-sky-600">Bad</span>
            </div>
          </div>
        )}

        {/* Canvas grid */}
        <div
          ref={containerRef}
          className="flex-1 min-h-0 overflow-auto rounded-2xl bg-slate-800/60 backdrop-blur-sm border border-white/20 relative"
        >
          <canvas
            ref={canvasRef}
            className="block cursor-crosshair"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
          />

          {/* Hover tooltip */}
          {tooltipData && (
            <div
              className="fixed z-50 pointer-events-none"
              style={{
                left: tooltipData.screenX + 16,
                top: tooltipData.screenY - 10,
              }}
            >
              <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg border border-slate-600 px-3 py-2 shadow-xl min-w-[160px]">
                <div className="text-xs font-bold text-slate-200 mb-1">
                  ({tooltipData.x}, {tooltipData.y}) {tooltipData.terrainName}
                </div>
                {tooltipData.gtProbs && (
                  <div className="mt-1">
                    <span className="text-[9px] text-slate-500 uppercase">Ground Truth</span>
                    <ProbBars probs={tooltipData.gtProbs} />
                  </div>
                )}
                {tooltipData.predProbs && (
                  <div className="mt-1">
                    <span className="text-[9px] text-slate-500 uppercase">Our Prediction</span>
                    <ProbBars probs={tooltipData.predProbs} />
                  </div>
                )}
                {!tooltipData.gtProbs && !tooltipData.predProbs && (
                  <span className="text-[10px] text-slate-500">No probability data</span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ═══════════════ RIGHT PANEL: Data & Stats ═══════════════ */}
      <div className="flex-[2] bg-slate-900 border-l border-slate-700 overflow-y-auto p-4 space-y-5">
        {/* Round selector */}
        <div>
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Round</h4>
          <select
            value={selectedRound}
            onChange={(e) => setSelectedRound(e.target.value)}
            className="w-full bg-slate-800 text-slate-200 text-sm rounded-lg border border-slate-600 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {sortedRoundKeys.map((key) => {
              const rd = terrainData.rounds[key];
              if (!rd) return null;
              const ri = roundsData.rounds.find((r) => r.round_number === rd.round_number);
              const scoreStr = ri?.our_score !== null && ri?.our_score !== undefined
                ? ` (${ri.our_score.toFixed(1)})`
                : "";
              const statusStr = rd.status === "active" ? " [ACTIVE]" : "";
              return (
                <option key={key} value={key}>
                  Round {rd.round_number}{scoreStr}{statusStr}
                </option>
              );
            })}
          </select>
        </div>

        {/* Seed tabs */}
        <div>
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Seed</h4>
          <div className="flex gap-1">
            {Array.from({ length: 5 }, (_, i) => {
              const hasSeed = currentRound && currentRound.seeds.length > i;
              let seedStyle = "bg-slate-800/50 text-slate-600 cursor-not-allowed";
              if (selectedSeed === i) {
                seedStyle = "bg-sky-600 text-white shadow-lg";
              } else if (hasSeed) {
                seedStyle = "bg-slate-800 text-slate-300 hover:bg-slate-700";
              }
              return (
                <button
                  key={i}
                  onClick={() => setSelectedSeed(i)}
                  disabled={!hasSeed}
                  className={`flex-1 px-2 py-2 rounded-lg text-xs font-bold transition-all ${seedStyle}`}
                >
                  S{i}
                </button>
              );
            })}
          </div>
          {/* Seed score */}
          {seedScores && seedScores[selectedSeed] !== undefined && (
            <div className="mt-1 text-xs text-slate-400">
              Seed score: <span className="text-sky-400 font-bold">{seedScores[selectedSeed]?.toFixed(2)}</span>
            </div>
          )}
        </div>

        {/* Score card */}
        <div className="rounded-xl bg-slate-800/80 border border-slate-700 p-4">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
            Round {roundNumber} Score
          </h4>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-sky-400 font-[Fredoka]">
              {roundInfo?.our_score !== null && roundInfo?.our_score !== undefined
                ? roundInfo.our_score.toFixed(1)
                : "--"}
            </span>
            <span className="text-sm text-slate-500">/ 100</span>
          </div>
          <div className="mt-2 flex gap-4 text-xs">
            <div>
              <span className="text-slate-500">Rank: </span>
              <span className="text-slate-300 font-semibold">
                {roundInfo?.our_rank ?? "--"}{roundInfo?.total_teams ? `/${roundInfo.total_teams}` : ""}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Weight: </span>
              <span className="text-slate-300 font-semibold">
                {roundInfo?.round_weight?.toFixed(2) ?? "--"}x
              </span>
            </div>
          </div>
          <div className="mt-1 flex gap-4 text-xs">
            <div>
              <span className="text-slate-500">Status: </span>
              <span className={`font-semibold ${
                currentRound?.status === "active" ? "text-green-400" : "text-slate-300"
              }`}>
                {currentRound?.status ?? "--"}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Queries: </span>
              <span className="text-slate-300 font-semibold">
                {roundInfo?.queries_used ?? 0}/{roundInfo?.queries_total ?? 50}
              </span>
            </div>
          </div>
        </div>

        {/* Coverage stats */}
        <div className="rounded-xl bg-slate-800/80 border border-slate-700 p-4">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
            Coverage
          </h4>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-sky-400 font-[Fredoka]">
              {coverage.observed}
            </span>
            <span className="text-sm text-slate-500">/ {coverage.total} cells</span>
          </div>
          <div className="mt-2 h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-sky-500 rounded-full transition-all duration-300"
              style={{ width: `${(coverage.observed / coverage.total) * 100}%` }}
            />
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {((coverage.observed / coverage.total) * 100).toFixed(1)}% coverage
          </div>
          <div className="mt-2 flex gap-3 text-xs">
            <div>
              <span className="text-slate-500">GT: </span>
              <span className={hasGT ? "text-green-400 font-semibold" : "text-slate-600"}>
                {hasGT ? "Available" : "None"}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Pred: </span>
              <span className={hasPred ? "text-green-400 font-semibold" : "text-slate-600"}>
                {hasPred ? "Available" : "None"}
              </span>
            </div>
          </div>
        </div>

        {/* Terrain legend with counts */}
        <div className="rounded-xl bg-slate-800/80 border border-slate-700 p-4">
          <DarkTerrainLegend entries={legendEntries} />
        </div>

        {/* Score sparkline */}
        {scoreHistory.length > 0 && (
          <div className="rounded-xl bg-slate-800/80 border border-slate-700 p-4">
            <ScoreSparkline scores={scoreHistory} />
          </div>
        )}

        {/* Terrain distribution */}
        {hasData && viewMode !== "initial" && !isPlaying && (
          <div className="rounded-xl bg-slate-800/80 border border-slate-700 p-4">
            <DistributionBars counts={terrainCounts} />
          </div>
        )}

        {/* Data quality info */}
        <div className="text-[10px] text-slate-600 space-y-0.5">
          <div>Terrain data: {terrainData.last_fetched.slice(0, 19).replace("T", " ")} UTC</div>
          <div>Rounds data: {roundsData.last_fetched.slice(0, 19).replace("T", " ")} UTC</div>
        </div>
      </div>
    </div>
  );
}
