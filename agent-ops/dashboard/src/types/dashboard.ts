export type DashboardTab = "overview" | "ml" | "cv" | "nlp";

/** Terrain types from Astar Island simulator */
export const TERRAIN_NAMES: Record<number, string> = {
  0: "Empty",
  1: "Settlement",
  2: "Port",
  3: "Ruin",
  4: "Forest",
  5: "Mountain",
  10: "Ocean",
  11: "Plains",
};

/** Raw terrain code to display class (6 classes for prediction) */
export const TERRAIN_TO_CLASS: Record<number, number> = {
  0: 0,   // Empty
  1: 1,   // Settlement
  2: 2,   // Port
  3: 3,   // Ruin
  4: 4,   // Forest
  5: 5,   // Mountain
  10: 0,  // Ocean -> Empty (for prediction class)
  11: 0,  // Plains -> Empty (for prediction class)
};

export interface SeedData {
  grid: number[][];
}

export interface RoundData {
  round_number: number;
  width: number;
  height: number;
  seeds: SeedData[];
}

export interface VizData {
  [key: string]: RoundData | { [seedKey: string]: number[][] };
}

export interface CVMetric {
  epoch: number;
  mAP50: number;
  mAP5095: number;
  precision: number;
  recall: number;
}

export interface NLPTaskStatus {
  taskType: string;
  tested: boolean;
  passing: boolean;
  score: number | null;
  tier: number;
}

export interface TrackScore {
  track: string;
  score: number;
  maxScore: number;
  submissions: number;
  lastSubmission: string | null;
}
