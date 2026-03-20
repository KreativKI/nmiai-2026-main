import { TERRAIN_COLORS } from "../canvas/terrainColors";

const LEGEND_ITEMS = [
  { code: 0, name: "Empty", color: TERRAIN_COLORS[0]! },
  { code: 1, name: "Settlement", color: TERRAIN_COLORS[1]! },
  { code: 2, name: "Port", color: TERRAIN_COLORS[2]! },
  { code: 3, name: "Ruin", color: TERRAIN_COLORS[3]! },
  { code: 4, name: "Forest", color: TERRAIN_COLORS[4]! },
  { code: 5, name: "Mountain", color: TERRAIN_COLORS[5]! },
  { code: 10, name: "Ocean", color: TERRAIN_COLORS[10]! },
  { code: 11, name: "Plains", color: TERRAIN_COLORS[11]! },
];

export function TerrainLegend() {
  return (
    <div className="flex flex-wrap gap-3">
      {LEGEND_ITEMS.map((item) => (
        <div key={item.code} className="flex items-center gap-1.5">
          <div
            className="w-4 h-4 rounded border border-white/30"
            style={{ backgroundColor: item.color }}
          />
          <span className="text-xs text-sky-700">{item.name}</span>
        </div>
      ))}
    </div>
  );
}
