import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useUIStore } from "../stores/uiStore";
import { TerrainGrid } from "./TerrainGrid";
import { TerrainLegend } from "./TerrainLegend";
import { MetricCard } from "./MetricCard";

type ViewMode = "initial" | "ground_truth" | "diff" | "animate";

interface SeedGT {
  initial_grid: number[][];
  ground_truth: number[][][]; // 40x40x6 probability distributions
}

interface GTRound {
  round_number: number;
  seeds: SeedGT[];
}

interface RoundSeed {
  grid: number[][];
}

interface RoundInfo {
  round_number: number;
  width: number;
  height: number;
  seeds: RoundSeed[];
}

interface VizFile {
  [key: string]: RoundInfo | GTRound[];
}

const TERRAIN_TO_CLASS: Record<number, number> = { 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 10: 0, 11: 0 };

/** Convert probability distribution (6-class) to argmax terrain type */
function probToTerrain(probs: number[]): number {
  let maxIdx = 0;
  let maxVal = probs[0] ?? 0;
  for (let i = 1; i < probs.length; i++) {
    const v = probs[i] ?? 0;
    if (v > maxVal) { maxVal = v; maxIdx = i; }
  }
  return maxIdx; // Class index IS the terrain code for classes 0-5
}

/** Create diff grid: -1 = unchanged, terrain code = changed to this */
function createDiffGrid(initial: number[][], gtProbs: number[][][]): number[][] {
  return initial.map((row, y) =>
    row.map((initTerrain, x) => {
      const probs = gtProbs[y]?.[x];
      if (!probs) return -1;
      const finalTerrain = probToTerrain(probs);
      const initClass = TERRAIN_TO_CLASS[initTerrain] ?? 0;
      return initClass === finalTerrain ? -1 : finalTerrain;
    })
  );
}

/**
 * Create interpolated grid for animation.
 * At progress=0 shows initial terrain, at progress=1 shows ground truth.
 * Cells that don't change stay as initial.
 * Cells that do change: at the moment progress crosses their threshold, they flip.
 * Threshold is randomized per-cell for a natural "spreading" effect.
 */
function createAnimatedGrid(
  initial: number[][],
  gtProbs: number[][][],
  thresholds: number[][],
  progress: number,
): number[][] {
  return initial.map((row, y) =>
    row.map((initTerrain, x) => {
      const probs = gtProbs[y]?.[x];
      if (!probs) return initTerrain;
      const finalTerrain = probToTerrain(probs);
      const initClass = TERRAIN_TO_CLASS[initTerrain] ?? 0;
      if (initClass === finalTerrain) return initTerrain;
      // Flip at this cell's threshold
      return progress >= (thresholds[y]?.[x] ?? 0.5) ? finalTerrain : initTerrain;
    })
  );
}

/** Generate stable random thresholds per cell (seeded by position) */
function generateThresholds(height: number, width: number): number[][] {
  const thresholds: number[][] = [];
  for (let y = 0; y < height; y++) {
    const row: number[] = [];
    for (let x = 0; x < width; x++) {
      // Simple hash for deterministic but spread-out thresholds
      const hash = Math.sin(y * 127.1 + x * 311.7) * 43758.5453;
      row.push((hash - Math.floor(hash)) * 0.85 + 0.05); // Range 0.05-0.90
    }
    thresholds.push(row);
  }
  return thresholds;
}

export function MLView() {
  const selectedSeed = useUIStore((s) => s.selectedSeed);
  const setSelectedSeed = useUIStore((s) => s.setSelectedSeed);

  const [vizData, setVizData] = useState<VizFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("initial");
  const [selectedGTRound, setSelectedGTRound] = useState(0);
  const [animProgress, setAnimProgress] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const animRef = useRef<number>(0);
  const progressRef = useRef(0);

  useEffect(() => {
    fetch("/data/viz_data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setVizData(d as VizFile))
      .catch((e) => setError(String(e)));
  }, []);

  // Parse data
  const { roundData, gtRounds } = useMemo(() => {
    if (!vizData) return { roundData: null, gtRounds: [] as GTRound[] };
    const rKeys = Object.keys(vizData).filter((k) => k.startsWith("round"));
    const latestKey = rKeys
      .sort((a, b) => (parseInt(a.replace(/\D/g, ""), 10) || 0) - (parseInt(b.replace(/\D/g, ""), 10) || 0))
      .pop();
    const rd = latestKey ? (vizData[latestKey] as RoundInfo) : null;
    const gt = (vizData["ground_truth"] ?? []) as GTRound[];
    return { roundData: rd, gtRounds: gt };
  }, [vizData]);

  const initialGrid = useMemo(() => roundData?.seeds[selectedSeed]?.grid ?? [], [roundData, selectedSeed]);
  const currentGTRound = gtRounds[selectedGTRound];
  const currentGTSeed = currentGTRound?.seeds[selectedSeed];

  const gtArgmaxGrid = useMemo(() => {
    if (!currentGTSeed?.ground_truth) return [];
    return currentGTSeed.ground_truth.map((row) => row.map(probToTerrain));
  }, [currentGTSeed]);

  const diffGrid = useMemo(() => {
    if (!currentGTSeed?.initial_grid || !currentGTSeed?.ground_truth) return [];
    return createDiffGrid(currentGTSeed.initial_grid, currentGTSeed.ground_truth);
  }, [currentGTSeed]);

  const changedCells = useMemo(() =>
    diffGrid.reduce((sum, row) => sum + row.filter((v) => v !== -1).length, 0),
  [diffGrid]);

  // Animation thresholds (stable per seed)
  const thresholds = useMemo(() => generateThresholds(40, 40), []);

  // Animated grid
  const animatedGrid = useMemo(() => {
    if (!currentGTSeed?.initial_grid || !currentGTSeed?.ground_truth) return initialGrid;
    return createAnimatedGrid(currentGTSeed.initial_grid, currentGTSeed.ground_truth, thresholds, animProgress);
  }, [currentGTSeed, initialGrid, thresholds, animProgress]);

  // Animation loop
  const animate = useCallback(() => {
    progressRef.current += 0.008; // ~6 seconds for full transition at 60fps
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
    setViewMode("animate");
    animRef.current = requestAnimationFrame(animate);
  }, [animate]);

  // Cleanup animation on unmount
  useEffect(() => () => cancelAnimationFrame(animRef.current), []);

  // Stop animation when switching modes
  useEffect(() => {
    if (viewMode !== "animate") {
      cancelAnimationFrame(animRef.current);
      setIsPlaying(false);
    }
  }, [viewMode]);

  // Which grid to display
  const displayGrid = viewMode === "initial" ? initialGrid
    : viewMode === "ground_truth" ? gtArgmaxGrid
    : viewMode === "diff" ? diffGrid
    : animatedGrid;

  const yearDisplay = viewMode === "animate" ? Math.round(animProgress * 50) : viewMode === "ground_truth" ? 50 : 0;

  const displayLabel = viewMode === "initial"
    ? `Seed ${selectedSeed} | Year 0 (Initial)`
    : viewMode === "ground_truth"
      ? `Seed ${selectedSeed} | Year 50 (Ground Truth) | Round ${currentGTRound?.round_number ?? "?"}`
      : viewMode === "diff"
        ? `Seed ${selectedSeed} | ${changedCells}/1600 cells changed`
        : `Seed ${selectedSeed} | Year ${yearDisplay} | ${Math.round(animProgress * 100)}%`;

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

  if (!vizData) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sky-500 animate-pulse">Loading terrain data...</p>
      </div>
    );
  }

  const hasGT = gtRounds.length > 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-sky-800 font-[Fredoka]">
            Astar Island - Terrain Prediction
          </h2>
          <p className="text-xs text-sky-500">
            40x40 grid, 6 terrain types, {roundData?.seeds.length ?? 0} seeds
          </p>
        </div>
        {/* Play animation button */}
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

      {/* View mode selector + animation progress */}
      <div className="flex gap-2 items-center flex-wrap">
        <span className="text-xs text-sky-600 font-semibold">View:</span>
        {(["initial", "ground_truth", "diff"] as ViewMode[]).map((mode) => {
          const labels: Record<string, string> = {
            initial: "Year 0",
            ground_truth: "Year 50",
            diff: "Changes",
          };
          const enabled = mode === "initial" || hasGT;
          return (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              disabled={!enabled}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                viewMode === mode
                  ? "bg-sky-800 text-white shadow-md"
                  : enabled
                    ? "bg-white/60 text-sky-700 hover:bg-white/80"
                    : "bg-white/30 text-sky-400 cursor-not-allowed"
              }`}
            >
              {labels[mode]}
            </button>
          );
        })}

        {/* Animation progress bar */}
        {viewMode === "animate" && (
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

        {/* GT round selector */}
        {gtRounds.length > 1 && viewMode !== "initial" && viewMode !== "animate" && (
          <>
            <span className="text-xs text-sky-400 ml-2">Round:</span>
            {gtRounds.map((gt, i) => (
              <button
                key={i}
                onClick={() => setSelectedGTRound(i)}
                className={`px-2 py-1 rounded text-xs font-semibold transition-all ${
                  selectedGTRound === i ? "bg-sky-700 text-white" : "bg-white/50 text-sky-600 hover:bg-white/70"
                }`}
              >
                R{gt.round_number}
              </button>
            ))}
          </>
        )}
      </div>

      {/* Metrics */}
      <div className="flex gap-3 flex-wrap">
        <MetricCard label="Seeds" value={roundData?.seeds.length ?? 0} subtitle="of 5 total" />
        <MetricCard label="GT Rounds" value={gtRounds.length} subtitle="available" />
        {(viewMode === "diff" || viewMode === "animate") && (
          <MetricCard
            label="Changed"
            value={changedCells}
            subtitle={`of 1600 (${((changedCells / 1600) * 100).toFixed(0)}%)`}
            color={changedCells > 800 ? "text-red-600" : "text-amber-600"}
          />
        )}
        {viewMode === "animate" && (
          <MetricCard label="Year" value={yearDisplay} subtitle="of 50" />
        )}
      </div>

      {/* Seed selector */}
      <div className="flex gap-2">
        {Array.from({ length: 5 }, (_, i) => (
          <button
            key={i}
            onClick={() => setSelectedSeed(i)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
              selectedSeed === i
                ? "bg-sky-800 text-white shadow-md"
                : "bg-white/60 text-sky-700 hover:bg-white/80"
            }`}
          >
            Seed {i}
          </button>
        ))}
      </div>

      <TerrainLegend />

      {/* Grid viewer */}
      <div className="flex-1 min-h-0">
        {displayGrid.length > 0 ? (
          <TerrainGrid
            grid={displayGrid}
            label={displayLabel}
            isDiffMode={viewMode === "diff"}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-sky-400">
            {!hasGT && viewMode !== "initial"
              ? "No ground truth data available yet"
              : `No data for seed ${selectedSeed}`}
          </div>
        )}
      </div>
    </div>
  );
}
