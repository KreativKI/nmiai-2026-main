/** Terrain type to display color mapping */
export const TERRAIN_COLORS: Record<number, string> = {
  0: "#f5f0e1",   // Empty: light beige
  1: "#a0845c",   // Settlement: brown
  2: "#4a9eda",   // Port: blue
  3: "#c45c5c",   // Ruin: red
  4: "#5a9e5a",   // Forest: green
  5: "#8a8a8a",   // Mountain: gray
  10: "#2a5a8a",  // Ocean: dark blue
  11: "#e8e0c8",  // Plains: slightly different beige
};

export const GRID_COLORS = {
  background: "#1e293b",   // slate-800
  gridLine: "rgba(255,255,255,0.08)",
  coordLabel: "#7dd3fc",
} as const;

export function terrainColor(type: number): string {
  return TERRAIN_COLORS[type] ?? "#666666";
}
