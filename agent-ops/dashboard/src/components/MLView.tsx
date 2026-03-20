import { useState, useEffect } from "react";
import { useUIStore } from "../stores/uiStore";
import { TerrainGrid } from "./TerrainGrid";
import { TerrainLegend } from "./TerrainLegend";
import { MetricCard } from "./MetricCard";
import type { VizData, RoundData, SeedData } from "../types/dashboard";

export function MLView() {
  const selectedSeed = useUIStore((s) => s.selectedSeed);
  const setSelectedSeed = useUIStore((s) => s.setSelectedSeed);
  const showGT = useUIStore((s) => s.showGroundTruth);
  const toggleGT = useUIStore((s) => s.toggleGroundTruth);

  const [vizData, setVizData] = useState<VizData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/data/viz_data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => setVizData(d as VizData))
      .catch((e) => setError(String(e)));
  }, []);

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

  // Parse viz data: find latest round and ground truth
  const roundKeys = Object.keys(vizData).filter((k) => k.startsWith("round"));
  const latestRound = roundKeys
    .sort((a, b) => {
      const numA = parseInt(a.replace(/\D/g, ""), 10) || 0;
      const numB = parseInt(b.replace(/\D/g, ""), 10) || 0;
      return numA - numB;
    })
    .pop();
  const roundData = latestRound ? (vizData[latestRound] as RoundData) : null;
  const groundTruth = vizData["ground_truth"] as { [key: string]: number[][] } | undefined;

  const seeds: SeedData[] = roundData?.seeds ?? [];
  const currentSeed = seeds[selectedSeed];
  const currentGrid = currentSeed?.grid ?? [];

  // Ground truth for selected seed
  const gtGrid = groundTruth?.[`seed_${selectedSeed}`] ?? null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden p-6 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-sky-800 font-[Fredoka]">
            Astar Island - Terrain Prediction
          </h2>
          <p className="text-xs text-sky-500">
            40x40 grid, 6 terrain types, {seeds.length} seeds
            {latestRound && ` | ${latestRound}`}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          {/* Ground truth toggle */}
          {groundTruth && (
            <button
              onClick={toggleGT}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                showGT
                  ? "bg-sky-800 text-white"
                  : "bg-white/60 text-sky-600 hover:bg-white/80"
              }`}
            >
              {showGT ? "Hide" : "Show"} Ground Truth
            </button>
          )}
        </div>
      </div>

      {/* Metrics row */}
      <div className="flex gap-3">
        <MetricCard label="Round" value={roundData?.round_number ?? "-"} subtitle={`${roundKeys.length} captured`} />
        <MetricCard label="Grid Size" value={`${roundData?.width ?? 40}x${roundData?.height ?? 40}`} />
        <MetricCard label="Seeds" value={seeds.length} subtitle="of 5 total" />
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
                : seeds[i]
                  ? "bg-white/60 text-sky-700 hover:bg-white/80"
                  : "bg-white/30 text-sky-400 cursor-not-allowed"
            }`}
            disabled={!seeds[i]}
          >
            Seed {i}
          </button>
        ))}
      </div>

      {/* Legend */}
      <TerrainLegend />

      {/* Grid viewer */}
      <div className="flex-1 min-h-0">
        {currentGrid.length > 0 ? (
          <TerrainGrid
            grid={currentGrid}
            groundTruth={gtGrid}
            label={`Seed ${selectedSeed} | Initial Terrain`}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-sky-400">
            No data for seed {selectedSeed}
          </div>
        )}
      </div>
    </div>
  );
}
