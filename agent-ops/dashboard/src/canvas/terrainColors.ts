/** Terrain type to display color mapping (matches tile sprite palette) */
export const TERRAIN_COLORS: Record<number, string> = {
  0: "#c4a882",   // Empty: sandy tan
  1: "#8b6914",   // Settlement: Norse wood brown
  2: "#1a4b8c",   // Port: dock blue
  3: "#5a5a5a",   // Ruin: stone grey
  4: "#1a5c2a",   // Forest: dark pine green
  5: "#6a6a6a",   // Mountain: rock grey
  10: "#143d6e",  // Ocean: deep blue
  11: "#c4a882",  // Plains: sandy tan (same as Empty)
};

export const GRID_COLORS = {
  background: "#1e293b",   // slate-800
  gridLine: "rgba(255,255,255,0.08)",
  coordLabel: "#7dd3fc",
} as const;

export function terrainColor(type: number): string {
  return TERRAIN_COLORS[type] ?? "#666666";
}
