import { useState, useEffect, useMemo } from "react";
import { useUIStore } from "../stores/uiStore";
import { TerrainGrid } from "./TerrainGrid";
import { TerrainLegend } from "./TerrainLegend";
import { MetricCard } from "./MetricCard";

type ViewMode = "initial" | "ground_truth" | "diff";

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

/** Convert probability distribution (6-class) to argmax terrain type */
function probToTerrain(probs: number[]): number {
  // Classes: 0=Empty, 1=Settlement, 2=Port, 3=Ruin, 4=Forest, 5=Mountain
  // Map back to raw terrain codes for display
  const CLASS_TO_TERRAIN = [0, 1, 2, 3, 4, 5];
  let maxIdx = 0;
  let maxVal = probs[0] ?? 0;
  for (let i = 1; i < probs.length; i++) {
    const v = probs[i] ?? 0;
    if (v > maxVal) {
      maxVal = v;
      maxIdx = i;
    }
  }
  return CLASS_TO_TERRAIN[maxIdx] ?? 0;
}

/** Create diff grid: 0 = unchanged, terrain code = changed to this */
function createDiffGrid(initial: number[][], gtProbs: number[][][]): number[][] {
  // Returns a grid where:
  // -1 = unchanged cell
  // terrain code = cell changed to this terrain
  const height = initial.length;
  const width = initial[0]?.length ?? 0;
  const diff: number[][] = [];
  for (let y = 0; y < height; y++) {
    const row: number[] = [];
    for (let x = 0; x < width; x++) {
      const initTerrain = initial[y]?.[x] ?? 0;
      const probs = gtProbs[y]?.[x];
      if (!probs) { row.push(-1); continue; }
      const finalTerrain = probToTerrain(probs);
      // Map initial terrain to class for comparison
      const TERRAIN_TO_CLASS: Record<number, number> = { 0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 10: 0, 11: 0 };
      const initClass = TERRAIN_TO_CLASS[initTerrain] ?? 0;
      row.push(initClass === finalTerrain ? -1 : finalTerrain);
    }
    diff.push(row);
  }
  return diff;
}

export function MLView() {
  const selectedSeed = useUIStore((s) => s.selectedSeed);
  const setSelectedSeed = useUIStore((s) => s.setSelectedSeed);

  const [vizData, setVizData] = useState<VizFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("initial");
  const [selectedGTRound, setSelectedGTRound] = useState(0);

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
  const { roundData, gtRounds, roundKeys } = useMemo(() => {
    if (!vizData) return { roundData: null, gtRounds: [] as GTRound[], roundKeys: [] as string[] };
    const rKeys = Object.keys(vizData).filter((k) => k.startsWith("round"));
    const latestKey = rKeys
      .sort((a, b) => {
        const numA = parseInt(a.replace(/\D/g, ""), 10) || 0;
        const numB = parseInt(b.replace(/\D/g, ""), 10) || 0;
        return numA - numB;
      })
      .pop();
    const rd = latestKey ? (vizData[latestKey] as RoundInfo) : null;
    const gt = (vizData["ground_truth"] ?? []) as GTRound[];
    return { roundData: rd, gtRounds: gt, roundKeys: rKeys };
  }, [vizData]);

  // Current seed grids
  const initialGrid = useMemo(() => {
    return roundData?.seeds[selectedSeed]?.grid ?? [];
  }, [roundData, selectedSeed]);

  const currentGTRound = gtRounds[selectedGTRound];
  const currentGTSeed = currentGTRound?.seeds[selectedSeed];

  // Ground truth argmax grid (convert probabilities to terrain codes)
  const gtArgmaxGrid = useMemo(() => {
    if (!currentGTSeed?.ground_truth) return [];
    return currentGTSeed.ground_truth.map((row) =>
      row.map((probs) => probToTerrain(probs))
    );
  }, [currentGTSeed]);

  // Diff grid
  const diffGrid = useMemo(() => {
    if (!currentGTSeed?.initial_grid || !currentGTSeed?.ground_truth) return [];
    return createDiffGrid(currentGTSeed.initial_grid, currentGTSeed.ground_truth);
  }, [currentGTSeed]);

  // Stats
  const changedCells = useMemo(() => {
    return diffGrid.reduce((sum, row) => sum + row.filter((v) => v !== -1).length, 0);
  }, [diffGrid]);

  // Which grid to display
  const displayGrid = viewMode === "initial" ? initialGrid
    : viewMode === "ground_truth" ? gtArgmaxGrid
    : diffGrid;

  const displayLabel = viewMode === "initial"
    ? `Seed ${selectedSeed} | Initial Terrain (Year 0)`
    : viewMode === "ground_truth"
      ? `Seed ${selectedSeed} | Ground Truth (Year 50) | Round ${currentGTRound?.round_number ?? "?"}`
      : `Seed ${selectedSeed} | Changes | ${changedCells}/1600 cells changed`;

  if (error) {
    return (
      <div className="flex-1 p-6">
        <div className="rounded-2xl bg-red-50/80 border border-red-200 p-6">
          <h3 className="text-lg font-bold text-red-800 font-[Fredoka]">Data Load Error</h3>
          <p className="text-sm text-red-600 mt-2">{error}</p>
          <p className="text-xs text-red-400 mt-1">
            Expected: public/data/viz_data.json (copy from agent-ml/solutions/data/)
          </p>
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
            {roundKeys.length > 0 && ` | ${roundKeys[roundKeys.length - 1]}`}
          </p>
        </div>
      </div>

      {/* View mode selector */}
      <div className="flex gap-2 items-center flex-wrap">
        <span className="text-xs text-sky-600 font-semibold">View:</span>
        {(["initial", "ground_truth", "diff"] as ViewMode[]).map((mode) => {
          const labels: Record<ViewMode, string> = {
            initial: "Initial (Year 0)",
            ground_truth: "Ground Truth (Year 50)",
            diff: "Changes",
          };
          const enabled = mode === "initial" || gtRounds.length > 0;
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

        {/* GT round selector */}
        {gtRounds.length > 1 && viewMode !== "initial" && (
          <>
            <span className="text-xs text-sky-400 ml-2">Round:</span>
            {gtRounds.map((gt, i) => (
              <button
                key={i}
                onClick={() => setSelectedGTRound(i)}
                className={`px-2 py-1 rounded text-xs font-semibold transition-all ${
                  selectedGTRound === i
                    ? "bg-sky-700 text-white"
                    : "bg-white/50 text-sky-600 hover:bg-white/70"
                }`}
              >
                R{gt.round_number}
              </button>
            ))}
          </>
        )}
      </div>

      {/* Metrics row */}
      <div className="flex gap-3 flex-wrap">
        <MetricCard label="Seeds" value={roundData?.seeds.length ?? 0} subtitle="of 5 total" />
        <MetricCard label="GT Rounds" value={gtRounds.length} subtitle="with ground truth" />
        {viewMode === "diff" && (
          <MetricCard
            label="Changed"
            value={changedCells}
            subtitle={`of 1600 (${((changedCells / 1600) * 100).toFixed(0)}%)`}
            color={changedCells > 800 ? "text-red-600" : "text-amber-600"}
          />
        )}
        <MetricCard label="Seed" value={selectedSeed} subtitle="selected" />
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

      {/* Legend */}
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
            {viewMode !== "initial" && gtRounds.length === 0
              ? "No ground truth data available yet"
              : `No data for seed ${selectedSeed}`}
          </div>
        )}
      </div>
    </div>
  );
}
