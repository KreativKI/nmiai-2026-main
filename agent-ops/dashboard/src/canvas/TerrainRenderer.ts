import { GRID_COLORS } from "./terrainColors";
import { getTile, TILE_SOURCE_SIZE, initTileCache } from "./terrainTiles";
import { TERRAIN_NAMES } from "../types/dashboard";

const CELL_SIZE = 16;
const HALF_CELL = CELL_SIZE / 2;
export const COORD_MARGIN = 24;

// Ensure tile cache is ready before first render
initTileCache();

export interface Camera {
  offsetX: number;
  offsetY: number;
  scale: number;
}

/**
 * Render a 40x40 terrain grid to canvas.
 * Pure function: no side effects beyond drawing.
 */
export function renderTerrainGrid(
  ctx: CanvasRenderingContext2D,
  grid: number[][],
  camera: Camera,
  canvasWidth: number,
  canvasHeight: number,
  groundTruth?: number[][] | null,
  isDiffMode?: boolean,
): void {
  const height = grid.length;
  const width = grid[0]?.length ?? 0;

  ctx.clearRect(0, 0, canvasWidth, canvasHeight);
  ctx.fillStyle = GRID_COLORS.background;
  ctx.fillRect(0, 0, canvasWidth, canvasHeight);

  ctx.save();
  ctx.translate(camera.offsetX, camera.offsetY);
  ctx.scale(camera.scale, camera.scale);
  ctx.translate(COORD_MARGIN, COORD_MARGIN);

  // Draw terrain cells
  for (let y = 0; y < height; y++) {
    const row = grid[y];
    if (!row) continue;
    for (let x = 0; x < width; x++) {
      const terrain = row[x];
      if (terrain === undefined) continue;
      const px = x * CELL_SIZE;
      const py = y * CELL_SIZE;

      if (isDiffMode && terrain === -1) {
        // Unchanged cell in diff mode: dark muted
        ctx.fillStyle = "#2a2a2a";
        ctx.fillRect(px, py, CELL_SIZE, CELL_SIZE);
      } else {
        // Draw pre-rendered tile sprite, scaled from TILE_SOURCE_SIZE to CELL_SIZE
        const tile = getTile(terrain);
        ctx.drawImage(tile, 0, 0, TILE_SOURCE_SIZE, TILE_SOURCE_SIZE, px, py, CELL_SIZE, CELL_SIZE);
        if (isDiffMode) {
          // Changed cell: bright border to highlight
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 1;
          ctx.strokeRect(px + 0.5, py + 0.5, CELL_SIZE - 1, CELL_SIZE - 1);
        }
      }

      // Subtle grid lines
      ctx.strokeStyle = GRID_COLORS.gridLine;
      ctx.lineWidth = 0.5;
      ctx.strokeRect(px, py, CELL_SIZE, CELL_SIZE);
    }
  }

  // Ground truth overlay (semi-transparent right half of each cell)
  if (groundTruth) {
    for (let y = 0; y < height; y++) {
      const row = groundTruth[y];
      if (!row) continue;
      for (let x = 0; x < width; x++) {
        const terrain = row[x];
        if (terrain === undefined) continue;
        const px = x * CELL_SIZE;
        const py = y * CELL_SIZE;

        // Draw ground truth on right half using tile sprite
        const gtTile = getTile(terrain);
        ctx.save();
        ctx.beginPath();
        ctx.rect(px + CELL_SIZE / 2, py, CELL_SIZE / 2, CELL_SIZE);
        ctx.clip();
        ctx.drawImage(gtTile, 0, 0, TILE_SOURCE_SIZE, TILE_SOURCE_SIZE, px, py, CELL_SIZE, CELL_SIZE);
        ctx.restore();

        // Divider line
        ctx.strokeStyle = "rgba(255,255,255,0.3)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px + CELL_SIZE / 2, py);
        ctx.lineTo(px + CELL_SIZE / 2, py + CELL_SIZE);
        ctx.stroke();
      }
    }
  }

  // Coordinate labels
  ctx.fillStyle = GRID_COLORS.coordLabel;
  ctx.font = "9px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  // Column numbers (every 5)
  for (let x = 0; x < width; x += 5) {
    ctx.fillText(String(x), x * CELL_SIZE + HALF_CELL, -COORD_MARGIN / 2);
  }
  // Row numbers (every 5)
  ctx.textAlign = "right";
  for (let y = 0; y < height; y += 5) {
    ctx.fillText(String(y), -COORD_MARGIN / 4, y * CELL_SIZE + HALF_CELL);
  }

  ctx.restore();
}

export function pixelToGrid(
  px: number,
  py: number,
  camera: Camera,
): [number, number] {
  const gx = Math.floor(((px - camera.offsetX) / camera.scale - COORD_MARGIN) / CELL_SIZE);
  const gy = Math.floor(((py - camera.offsetY) / camera.scale - COORD_MARGIN) / CELL_SIZE);
  return [gx, gy];
}

export function centerCamera(
  gridWidth: number,
  gridHeight: number,
  canvasWidth: number,
  canvasHeight: number,
  scale: number,
): Camera {
  const gridPixelW = (gridWidth * CELL_SIZE + COORD_MARGIN) * scale;
  const gridPixelH = (gridHeight * CELL_SIZE + COORD_MARGIN) * scale;
  return {
    offsetX: (canvasWidth - gridPixelW) / 2,
    offsetY: (canvasHeight - gridPixelH) / 2,
    scale,
  };
}

export function fitScale(
  gridWidth: number,
  gridHeight: number,
  canvasWidth: number,
  canvasHeight: number,
  padding = 20,
): number {
  const scaleX = (canvasWidth - padding * 2) / (gridWidth * CELL_SIZE + COORD_MARGIN);
  const scaleY = (canvasHeight - padding * 2) / (gridHeight * CELL_SIZE + COORD_MARGIN);
  return Math.min(scaleX, scaleY, 3);
}

/** Get terrain info string for a cell */
export function cellInfo(grid: number[][], x: number, y: number, isDiffMode?: boolean): string {
  const row = grid[y];
  if (!row) return "Out of bounds";
  const terrain = row[x];
  if (terrain === undefined) return "Out of bounds";
  if (isDiffMode && terrain === -1) return `(${x}, ${y}) Unchanged`;
  const name = TERRAIN_NAMES[terrain] ?? `Unknown(${terrain})`;
  if (isDiffMode) return `(${x}, ${y}) Changed to ${name}`;
  return `(${x}, ${y}) ${name}`;
}
