/**
 * Terrain tile sprites for the Astar Island map viewer.
 *
 * Each terrain type has a dedicated drawing function that renders a
 * 32x32 pixel sprite to an OffscreenCanvas at init time.  The renderer
 * then blits these cached bitmaps instead of flat-colored rectangles,
 * giving the map a rich, Norse-mythology pixel-art look.
 *
 * Design notes:
 *   - Top-down view, muted fantasy palette
 *   - Tileable: edges wrap seamlessly when placed in a grid
 *   - Consistent 32x32 source size, scaled down to CELL_SIZE at draw time
 */

const TILE_SZ = 32;

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------
const PAL = {
  ocean:      { deep: "#143d6e", mid: "#1a4b8c", light: "#2d6cb5", foam: "#5a9ad6" },
  empty:      { base: "#c4a882", dark: "#a8906a", speck: "#8a7456" },
  settlement: { wall: "#8b6914", roof: "#b84c3c", ground: "#a0937d", window: "#f2c94c" },
  port:       { water: "#1a4b8c", plank: "#6b4423", rope: "#a0845c", post: "#4a3218" },
  ruin:       { stone: "#5a5a5a", light: "#8a8a8a", moss: "#4a6a4a", shadow: "#3a3a3a" },
  forest:     { canopy: "#1a5c2a", light: "#2d8a3f", trunk: "#5c3a1e", floor: "#2a4a20" },
  mountain:   { rock: "#6a6a6a", light: "#9a9a9a", snow: "#d8d8e8", shadow: "#4a4a5a" },
  unknown:    { mist: "#5a3d7a", glow: "#8a6aaa", dark: "#3a2a5a", spark: "#b89ae0" },
} as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Seeded pseudo-random for deterministic tile patterns. */
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function createTileCanvas(): [OffscreenCanvas, OffscreenCanvasRenderingContext2D] {
  const c = new OffscreenCanvas(TILE_SZ, TILE_SZ);
  const ctx = c.getContext("2d")!;
  return [c, ctx];
}

// ---------------------------------------------------------------------------
// Individual tile painters
// ---------------------------------------------------------------------------

function drawOcean(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Base water
  ctx.fillStyle = PAL.ocean.deep;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Subtle depth variation bands
  ctx.fillStyle = PAL.ocean.mid;
  ctx.fillRect(0, 8, TILE_SZ, 6);
  ctx.fillRect(0, 22, TILE_SZ, 6);

  // Wave lines
  ctx.strokeStyle = PAL.ocean.light;
  ctx.lineWidth = 1;
  for (let row = 0; row < 4; row++) {
    const y = 4 + row * 8;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.quadraticCurveTo(8, y - 2, 16, y);
    ctx.quadraticCurveTo(24, y + 2, 32, y);
    ctx.stroke();
  }

  // Foam highlights
  const rng = seededRandom(42);
  ctx.fillStyle = PAL.ocean.foam;
  for (let i = 0; i < 6; i++) {
    const x = Math.floor(rng() * 30);
    const y = Math.floor(rng() * 30);
    ctx.fillRect(x, y, 2, 1);
  }

  return c;
}

function drawEmpty(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Sandy base
  ctx.fillStyle = PAL.empty.base;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Darker patches
  ctx.fillStyle = PAL.empty.dark;
  const rng = seededRandom(7);
  for (let i = 0; i < 8; i++) {
    const x = Math.floor(rng() * 28);
    const y = Math.floor(rng() * 28);
    ctx.fillRect(x, y, 3 + Math.floor(rng() * 4), 2 + Math.floor(rng() * 3));
  }

  // Specks (pebbles)
  ctx.fillStyle = PAL.empty.speck;
  for (let i = 0; i < 12; i++) {
    const x = Math.floor(rng() * 31);
    const y = Math.floor(rng() * 31);
    ctx.fillRect(x, y, 1, 1);
  }

  return c;
}

function drawSettlement(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Ground
  ctx.fillStyle = PAL.settlement.ground;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Norse longhouse (top-down view: rectangular with peaked roof line)
  // House body
  ctx.fillStyle = PAL.settlement.wall;
  ctx.fillRect(6, 8, 20, 16);

  // Roof ridge line (darker)
  ctx.fillStyle = PAL.settlement.roof;
  ctx.fillRect(6, 8, 20, 3);
  ctx.fillRect(6, 21, 20, 3);

  // Roof peak line
  ctx.strokeStyle = PAL.settlement.roof;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(16, 6);
  ctx.lineTo(16, 26);
  ctx.stroke();

  // Windows (two small yellow dots)
  ctx.fillStyle = PAL.settlement.window;
  ctx.fillRect(11, 14, 2, 2);
  ctx.fillRect(19, 14, 2, 2);

  // Door
  ctx.fillStyle = "#5a4010";
  ctx.fillRect(14, 18, 4, 4);

  // Path at bottom
  ctx.fillStyle = PAL.empty.dark;
  ctx.fillRect(13, 24, 6, 8);

  return c;
}

function drawPort(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Water background (left half)
  ctx.fillStyle = PAL.port.water;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Wave lines on water
  ctx.strokeStyle = PAL.ocean.light;
  ctx.lineWidth = 1;
  for (let row = 0; row < 4; row++) {
    const y = 4 + row * 8;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.quadraticCurveTo(4, y - 1, 8, y);
    ctx.stroke();
  }

  // Dock planks (right half)
  ctx.fillStyle = PAL.port.plank;
  ctx.fillRect(14, 0, 18, TILE_SZ);

  // Plank lines
  ctx.strokeStyle = PAL.port.post;
  ctx.lineWidth = 1;
  for (let y = 0; y < TILE_SZ; y += 4) {
    ctx.beginPath();
    ctx.moveTo(14, y);
    ctx.lineTo(32, y);
    ctx.stroke();
  }

  // Dock posts (vertical pillars)
  ctx.fillStyle = PAL.port.post;
  ctx.fillRect(13, 2, 3, 4);
  ctx.fillRect(13, 14, 3, 4);
  ctx.fillRect(13, 26, 3, 4);

  // Rope coil
  ctx.strokeStyle = PAL.port.rope;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(24, 16, 3, 0, Math.PI * 2);
  ctx.stroke();

  return c;
}

function drawRuin(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Ground
  ctx.fillStyle = PAL.empty.dark;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Broken walls (L-shapes, scattered blocks)
  ctx.fillStyle = PAL.ruin.stone;

  // Wall fragment 1 (bottom-left L)
  ctx.fillRect(3, 18, 12, 3);
  ctx.fillRect(3, 10, 3, 11);

  // Wall fragment 2 (top-right broken)
  ctx.fillRect(18, 4, 10, 3);
  ctx.fillRect(25, 4, 3, 10);

  // Scattered rubble blocks
  ctx.fillStyle = PAL.ruin.light;
  const rng = seededRandom(13);
  for (let i = 0; i < 8; i++) {
    const x = Math.floor(rng() * 28) + 2;
    const y = Math.floor(rng() * 28) + 2;
    const s = 1 + Math.floor(rng() * 3);
    ctx.fillRect(x, y, s, s);
  }

  // Moss patches
  ctx.fillStyle = PAL.ruin.moss;
  ctx.fillRect(5, 12, 2, 2);
  ctx.fillRect(20, 8, 3, 2);
  ctx.fillRect(10, 22, 2, 2);

  // Shadow under walls
  ctx.fillStyle = PAL.ruin.shadow;
  ctx.fillRect(4, 21, 10, 1);
  ctx.fillRect(19, 7, 8, 1);

  return c;
}

function drawForest(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Forest floor
  ctx.fillStyle = PAL.forest.floor;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Draw 3 pine trees from back to front (top-down: circular canopies with trunk visible at center)
  const trees = [
    { x: 8, y: 7, r: 7 },
    { x: 24, y: 10, r: 6 },
    { x: 14, y: 22, r: 8 },
  ];

  for (const t of trees) {
    // Trunk (small brown dot visible at center)
    ctx.fillStyle = PAL.forest.trunk;
    ctx.fillRect(t.x - 1, t.y - 1, 3, 3);

    // Canopy (overlapping circles)
    ctx.fillStyle = PAL.forest.canopy;
    ctx.beginPath();
    ctx.arc(t.x, t.y, t.r, 0, Math.PI * 2);
    ctx.fill();

    // Lighter highlight on canopy
    ctx.fillStyle = PAL.forest.light;
    ctx.beginPath();
    ctx.arc(t.x - 1, t.y - 1, t.r * 0.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // Small undergrowth specks
  const rng = seededRandom(99);
  ctx.fillStyle = PAL.forest.light;
  for (let i = 0; i < 6; i++) {
    ctx.fillRect(Math.floor(rng() * 30), Math.floor(rng() * 30), 2, 1);
  }

  return c;
}

function drawMountain(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Base rock
  ctx.fillStyle = PAL.mountain.shadow;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Mountain peak (triangle from above: looks like a diamond/rhombus)
  ctx.fillStyle = PAL.mountain.rock;
  ctx.beginPath();
  ctx.moveTo(16, 2);    // north point
  ctx.lineTo(30, 16);   // east
  ctx.lineTo(16, 30);   // south
  ctx.lineTo(2, 16);    // west
  ctx.closePath();
  ctx.fill();

  // Lighter face (NW)
  ctx.fillStyle = PAL.mountain.light;
  ctx.beginPath();
  ctx.moveTo(16, 2);
  ctx.lineTo(2, 16);
  ctx.lineTo(16, 16);
  ctx.closePath();
  ctx.fill();

  // Snow cap at peak
  ctx.fillStyle = PAL.mountain.snow;
  ctx.beginPath();
  ctx.moveTo(16, 4);
  ctx.lineTo(10, 12);
  ctx.lineTo(16, 12);
  ctx.lineTo(22, 12);
  ctx.closePath();
  ctx.fill();

  // Rocky texture
  const rng = seededRandom(55);
  ctx.fillStyle = PAL.mountain.shadow;
  for (let i = 0; i < 8; i++) {
    const x = 6 + Math.floor(rng() * 20);
    const y = 12 + Math.floor(rng() * 16);
    ctx.fillRect(x, y, 2, 1);
  }

  return c;
}

function drawUnknown(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  // Dark mystical base
  ctx.fillStyle = PAL.unknown.dark;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Fog swirls (concentric arcs)
  ctx.strokeStyle = PAL.unknown.mist;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(16, 16, 12, 0.3, 2.8);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(16, 16, 8, 3.5, 5.8);
  ctx.stroke();

  // Glowing wisps
  ctx.strokeStyle = PAL.unknown.glow;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(10, 10, 4, 0, 4);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(24, 22, 3, 1, 5);
  ctx.stroke();

  // Sparkle dots
  ctx.fillStyle = PAL.unknown.spark;
  const rng = seededRandom(77);
  for (let i = 0; i < 5; i++) {
    const x = 4 + Math.floor(rng() * 24);
    const y = 4 + Math.floor(rng() * 24);
    ctx.fillRect(x, y, 1, 1);
  }

  // Question mark silhouette
  ctx.fillStyle = PAL.unknown.spark;
  ctx.font = "bold 14px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.globalAlpha = 0.3;
  ctx.fillText("?", 16, 17);
  ctx.globalAlpha = 1;

  return c;
}

// ---------------------------------------------------------------------------
// Tile cache
// ---------------------------------------------------------------------------

/** Map from terrain type ID to its pre-rendered tile canvas. */
let tileCache: Map<number, OffscreenCanvas> | null = null;

/**
 * Initialise (or re-initialise) the tile sprite cache.
 * Call once at app startup before the first render frame.
 */
export function initTileCache(): void {
  tileCache = new Map<number, OffscreenCanvas>();

  tileCache.set(0,  drawEmpty());
  tileCache.set(1,  drawSettlement());
  tileCache.set(2,  drawPort());
  tileCache.set(3,  drawRuin());
  tileCache.set(4,  drawForest());
  tileCache.set(5,  drawMountain());
  tileCache.set(10, drawOcean());
  tileCache.set(11, drawEmpty());     // Plains reuses Empty tile

  // Unknown / fallback
  tileCache.set(-99, drawUnknown());
}

/**
 * Get the cached tile sprite for a terrain type.
 * Returns the "unknown" tile for unrecognised types.
 */
export function getTile(terrainType: number): OffscreenCanvas {
  if (!tileCache) initTileCache();
  return tileCache!.get(terrainType) ?? tileCache!.get(-99)!;
}

/** Source tile size (for drawImage scaling). */
export const TILE_SOURCE_SIZE = TILE_SZ;

/** The colour palette, exported for the legend component. */
export { PAL as TERRAIN_PALETTE };
