/**
 * Terrain tile sprites for the Astar Island map viewer.
 *
 * Each terrain type has a dedicated drawing function that renders a
 * 32x32 pixel sprite to an OffscreenCanvas at init time. The renderer
 * blits these cached bitmaps via drawImage().
 *
 * Design: Norse mythology pixel art, 16-bit era RPG style.
 * Palette: muted fantasy, cold blues, warm earth tones.
 */

const TILE_SZ = 32;

// ---------------------------------------------------------------------------
// Color palette — richer Norse fantasy tones
// ---------------------------------------------------------------------------
const PAL = {
  ocean:      { deep: "#0d2b4a", mid: "#143d6e", light: "#1e5a96", foam: "#4a8ac0", highlight: "#7ab4e0", dark: "#061a2e" },
  empty:      { base: "#b8a070", dark: "#9a7e52", light: "#d4c098", crack: "#7a6040", grass: "#6a8a4a", pebble: "#8a7456" },
  settlement: { wall: "#7a5a14", roof: "#a04030", thatch: "#8a6830", ground: "#9a8a6a", window: "#e8b830", smoke: "#b0b0b0", door: "#4a3010", foundation: "#6a6a5a" },
  port:       { water: "#143d6e", plank: "#5a3a1a", grain: "#4a2e12", post: "#3a2210", rope: "#8a6a40", boat: "#3a2a1a" },
  ruin:       { stone: "#5a5a5a", light: "#7a7a7a", moss: "#3a5a3a", shadow: "#2a2a2a", rubble: "#6a6a6a", grass: "#4a6a3a" },
  forest:     { canopy: "#14461e", light: "#1e6a2a", highlight: "#2a8a3a", trunk: "#4a2a10", floor: "#1a3a14", shadow: "#0e2a0e" },
  mountain:   { rock: "#5a5a5a", light: "#8a8a8a", snow: "#c8c8d8", shadow: "#3a3a4a", crevice: "#2a2a3a", ice: "#a0a8c0" },
  unknown:    { base: "#2a1a3a", mist: "#4a2a5a", glow: "#6a4a8a", spark: "#a080c0", deep: "#1a0e2a" },
} as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
// Individual tile painters (enhanced pixel art)
// ---------------------------------------------------------------------------

function drawOcean(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  const rng = seededRandom(42);

  // Deep base
  ctx.fillStyle = PAL.ocean.dark;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Depth bands (horizontal layers of varying blue)
  ctx.fillStyle = PAL.ocean.deep;
  ctx.fillRect(0, 0, TILE_SZ, 10);
  ctx.fillStyle = PAL.ocean.mid;
  ctx.fillRect(0, 10, TILE_SZ, 8);
  ctx.fillStyle = PAL.ocean.deep;
  ctx.fillRect(0, 18, TILE_SZ, 6);
  ctx.fillStyle = PAL.ocean.mid;
  ctx.fillRect(0, 24, TILE_SZ, 8);

  // Subtle noise texture
  ctx.globalAlpha = 0.15;
  ctx.fillStyle = PAL.ocean.light;
  for (let i = 0; i < 30; i++) {
    ctx.fillRect(Math.floor(rng() * 31), Math.floor(rng() * 31), 1, 1);
  }
  ctx.globalAlpha = 1;

  // Wave crests (curved light lines)
  ctx.strokeStyle = PAL.ocean.light;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.6;
  for (let row = 0; row < 4; row++) {
    const y = 3 + row * 8;
    const offset = row % 2 === 0 ? 0 : 8;
    ctx.beginPath();
    ctx.moveTo(offset, y);
    ctx.quadraticCurveTo(offset + 4, y - 2, offset + 8, y);
    ctx.quadraticCurveTo(offset + 12, y + 2, offset + 16, y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(offset + 16, y + 1);
    ctx.quadraticCurveTo(offset + 20, y - 1, offset + 24, y + 1);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Foam highlights (scattered white dots)
  ctx.fillStyle = PAL.ocean.highlight;
  ctx.globalAlpha = 0.4;
  for (let i = 0; i < 10; i++) {
    const x = Math.floor(rng() * 30) + 1;
    const y = Math.floor(rng() * 30) + 1;
    ctx.fillRect(x, y, 1 + Math.floor(rng() * 2), 1);
  }

  // Deep current streaks
  ctx.fillStyle = PAL.ocean.dark;
  ctx.globalAlpha = 0.3;
  for (let i = 0; i < 4; i++) {
    const x = Math.floor(rng() * 24) + 4;
    const y = Math.floor(rng() * 28) + 2;
    ctx.fillRect(x, y, 4 + Math.floor(rng() * 6), 1);
  }
  ctx.globalAlpha = 1;

  return c;
}

function drawEmpty(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  const rng = seededRandom(7);

  // Base sandy ground
  ctx.fillStyle = PAL.empty.base;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Darker earth patches (large)
  ctx.globalAlpha = 0.4;
  ctx.fillStyle = PAL.empty.dark;
  for (let i = 0; i < 6; i++) {
    const x = Math.floor(rng() * 26);
    const y = Math.floor(rng() * 26);
    ctx.fillRect(x, y, 4 + Math.floor(rng() * 6), 3 + Math.floor(rng() * 4));
  }

  // Lighter sandy highlights
  ctx.fillStyle = PAL.empty.light;
  ctx.globalAlpha = 0.3;
  for (let i = 0; i < 5; i++) {
    const x = Math.floor(rng() * 28);
    const y = Math.floor(rng() * 28);
    ctx.fillRect(x, y, 3 + Math.floor(rng() * 5), 2 + Math.floor(rng() * 3));
  }
  ctx.globalAlpha = 1;

  // Cracks in the earth
  ctx.strokeStyle = PAL.empty.crack;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.5;
  for (let i = 0; i < 3; i++) {
    const x1 = Math.floor(rng() * 20) + 6;
    const y1 = Math.floor(rng() * 20) + 6;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 + Math.floor(rng() * 8) - 4, y1 + Math.floor(rng() * 6) + 2);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Pebbles (1px dots)
  ctx.fillStyle = PAL.empty.pebble;
  for (let i = 0; i < 15; i++) {
    ctx.fillRect(Math.floor(rng() * 31), Math.floor(rng() * 31), 1, 1);
  }

  // Sparse grass tufts
  ctx.fillStyle = PAL.empty.grass;
  ctx.globalAlpha = 0.6;
  for (let i = 0; i < 4; i++) {
    const x = Math.floor(rng() * 28) + 2;
    const y = Math.floor(rng() * 28) + 2;
    ctx.fillRect(x, y, 1, 2);
    ctx.fillRect(x + 1, y + 1, 1, 1);
  }
  ctx.globalAlpha = 1;

  return c;
}

function drawSettlement(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();

  // Ground (warm earth)
  ctx.fillStyle = PAL.settlement.ground;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Ground texture
  const rng = seededRandom(33);
  ctx.globalAlpha = 0.2;
  ctx.fillStyle = PAL.empty.dark;
  for (let i = 0; i < 8; i++) {
    ctx.fillRect(Math.floor(rng() * 30), Math.floor(rng() * 30), 2, 1);
  }
  ctx.globalAlpha = 1;

  // Stone foundation
  ctx.fillStyle = PAL.settlement.foundation;
  ctx.fillRect(5, 7, 22, 18);

  // Norse longhouse body (wooden walls)
  ctx.fillStyle = PAL.settlement.wall;
  ctx.fillRect(6, 8, 20, 16);

  // Horizontal plank lines
  ctx.strokeStyle = PAL.settlement.thatch;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.4;
  for (let y = 10; y < 24; y += 3) {
    ctx.beginPath();
    ctx.moveTo(6, y);
    ctx.lineTo(26, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Thatched roof edges (top and bottom)
  ctx.fillStyle = PAL.settlement.roof;
  ctx.fillRect(5, 7, 22, 3);
  ctx.fillRect(5, 22, 22, 3);

  // Roof ridge line (center, dark)
  ctx.strokeStyle = PAL.settlement.thatch;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(16, 5);
  ctx.lineTo(16, 27);
  ctx.stroke();

  // Roof end gables
  ctx.fillStyle = PAL.settlement.roof;
  ctx.beginPath();
  ctx.moveTo(16, 5);
  ctx.lineTo(5, 8);
  ctx.lineTo(27, 8);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(16, 27);
  ctx.lineTo(5, 24);
  ctx.lineTo(27, 24);
  ctx.closePath();
  ctx.fill();

  // Windows (warm firelight glow)
  ctx.fillStyle = PAL.settlement.window;
  ctx.fillRect(10, 13, 3, 3);
  ctx.fillRect(19, 13, 3, 3);

  // Window glow effect
  ctx.globalAlpha = 0.3;
  ctx.fillStyle = PAL.settlement.window;
  ctx.fillRect(9, 12, 5, 5);
  ctx.fillRect(18, 12, 5, 5);
  ctx.globalAlpha = 1;

  // Door
  ctx.fillStyle = PAL.settlement.door;
  ctx.fillRect(14, 17, 4, 5);

  // Smoke wisps above
  ctx.fillStyle = PAL.settlement.smoke;
  ctx.globalAlpha = 0.3;
  ctx.fillRect(15, 2, 1, 2);
  ctx.fillRect(16, 1, 1, 2);
  ctx.fillRect(17, 3, 1, 1);
  ctx.globalAlpha = 1;

  // Path from door
  ctx.fillStyle = PAL.empty.dark;
  ctx.globalAlpha = 0.5;
  ctx.fillRect(14, 24, 4, 8);
  ctx.globalAlpha = 1;

  return c;
}

function drawPort(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  const rng = seededRandom(21);

  // Water background (left portion)
  ctx.fillStyle = PAL.ocean.deep;
  ctx.fillRect(0, 0, 14, TILE_SZ);

  // Water depth variation
  ctx.fillStyle = PAL.ocean.mid;
  ctx.fillRect(0, 6, 14, 6);
  ctx.fillRect(0, 20, 14, 6);

  // Water waves
  ctx.strokeStyle = PAL.ocean.light;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.5;
  for (let row = 0; row < 4; row++) {
    const y = 4 + row * 8;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.quadraticCurveTo(3, y - 1, 7, y);
    ctx.quadraticCurveTo(10, y + 1, 13, y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  // Dock planks (right portion)
  ctx.fillStyle = PAL.port.plank;
  ctx.fillRect(13, 0, 19, TILE_SZ);

  // Plank grain lines (horizontal)
  ctx.strokeStyle = PAL.port.grain;
  ctx.lineWidth = 1;
  for (let y = 0; y < TILE_SZ; y += 4) {
    ctx.beginPath();
    ctx.moveTo(13, y);
    ctx.lineTo(32, y);
    ctx.stroke();
  }

  // Wood texture (subtle variation)
  ctx.globalAlpha = 0.15;
  ctx.fillStyle = PAL.port.grain;
  for (let i = 0; i < 12; i++) {
    ctx.fillRect(14 + Math.floor(rng() * 16), Math.floor(rng() * 30), 1, 2);
  }
  ctx.globalAlpha = 1;

  // Dock edge posts (vertical pillars at water line)
  ctx.fillStyle = PAL.port.post;
  ctx.fillRect(12, 1, 3, 5);
  ctx.fillRect(12, 13, 3, 5);
  ctx.fillRect(12, 25, 3, 5);

  // Post tops (lighter)
  ctx.fillStyle = PAL.port.plank;
  ctx.fillRect(13, 1, 1, 1);
  ctx.fillRect(13, 13, 1, 1);
  ctx.fillRect(13, 25, 1, 1);

  // Rope coil on dock
  ctx.strokeStyle = PAL.port.rope;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(22, 10, 3, 0, Math.PI * 1.8);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(22, 10, 1.5, 0.5, Math.PI * 1.5);
  ctx.stroke();

  // Small boat silhouette (3-4 pixels)
  ctx.fillStyle = PAL.port.boat;
  ctx.fillRect(3, 14, 5, 2);
  ctx.fillRect(4, 13, 3, 1);
  ctx.fillRect(4, 16, 3, 1);

  // Water foam at dock edge
  ctx.fillStyle = PAL.ocean.foam;
  ctx.globalAlpha = 0.4;
  ctx.fillRect(11, 7, 2, 1);
  ctx.fillRect(11, 19, 2, 1);
  ctx.fillRect(11, 3, 1, 1);
  ctx.fillRect(11, 28, 2, 1);
  ctx.globalAlpha = 1;

  return c;
}

function drawRuin(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  const rng = seededRandom(13);

  // Overgrown ground base
  ctx.fillStyle = PAL.empty.dark;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Ground texture
  ctx.globalAlpha = 0.3;
  ctx.fillStyle = PAL.empty.base;
  for (let i = 0; i < 10; i++) {
    ctx.fillRect(Math.floor(rng() * 30), Math.floor(rng() * 30), 2 + Math.floor(rng() * 3), 2);
  }
  ctx.globalAlpha = 1;

  // Wall fragment 1 (bottom-left L-shape)
  ctx.fillStyle = PAL.ruin.stone;
  ctx.fillRect(2, 17, 13, 4);
  ctx.fillRect(2, 9, 4, 12);
  // Wall shadow
  ctx.fillStyle = PAL.ruin.shadow;
  ctx.fillRect(3, 21, 11, 1);
  ctx.fillRect(6, 10, 1, 8);

  // Wall top highlight
  ctx.fillStyle = PAL.ruin.light;
  ctx.fillRect(2, 17, 13, 1);
  ctx.fillRect(2, 9, 4, 1);

  // Wall fragment 2 (top-right broken)
  ctx.fillStyle = PAL.ruin.stone;
  ctx.fillRect(17, 3, 11, 4);
  ctx.fillRect(24, 3, 4, 11);
  // Shadow
  ctx.fillStyle = PAL.ruin.shadow;
  ctx.fillRect(18, 7, 9, 1);
  ctx.fillRect(24, 14, 1, 1);
  // Highlight
  ctx.fillStyle = PAL.ruin.light;
  ctx.fillRect(17, 3, 11, 1);

  // Scattered rubble blocks
  ctx.fillStyle = PAL.ruin.rubble;
  for (let i = 0; i < 12; i++) {
    const x = Math.floor(rng() * 26) + 3;
    const y = Math.floor(rng() * 26) + 3;
    const s = 1 + Math.floor(rng() * 3);
    ctx.fillRect(x, y, s, s);
  }

  // Stone texture on walls
  ctx.globalAlpha = 0.3;
  ctx.fillStyle = PAL.ruin.light;
  for (let i = 0; i < 6; i++) {
    ctx.fillRect(3 + Math.floor(rng() * 10), 10 + Math.floor(rng() * 8), 2, 1);
    ctx.fillRect(18 + Math.floor(rng() * 8), 4 + Math.floor(rng() * 8), 2, 1);
  }
  ctx.globalAlpha = 1;

  // Moss patches (green on stone)
  ctx.fillStyle = PAL.ruin.moss;
  ctx.fillRect(4, 12, 3, 2);
  ctx.fillRect(6, 18, 2, 2);
  ctx.fillRect(20, 5, 3, 2);
  ctx.fillRect(26, 8, 2, 3);

  // Grass pushing through cracks
  ctx.fillStyle = PAL.ruin.grass;
  ctx.globalAlpha = 0.7;
  for (let i = 0; i < 6; i++) {
    const x = Math.floor(rng() * 28) + 2;
    const y = Math.floor(rng() * 28) + 2;
    ctx.fillRect(x, y, 1, 2);
    ctx.fillRect(x + 1, y, 1, 3);
  }
  ctx.globalAlpha = 1;

  return c;
}

function drawForest(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  const rng = seededRandom(99);

  // Dark forest floor
  ctx.fillStyle = PAL.forest.floor;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Forest floor shadow variation
  ctx.fillStyle = PAL.forest.shadow;
  ctx.globalAlpha = 0.5;
  for (let i = 0; i < 12; i++) {
    ctx.fillRect(Math.floor(rng() * 30), Math.floor(rng() * 30), 3 + Math.floor(rng() * 4), 2 + Math.floor(rng() * 3));
  }
  ctx.globalAlpha = 1;

  // Undergrowth texture
  ctx.fillStyle = PAL.forest.light;
  ctx.globalAlpha = 0.2;
  for (let i = 0; i < 8; i++) {
    ctx.fillRect(Math.floor(rng() * 30), Math.floor(rng() * 30), 2, 1);
  }
  ctx.globalAlpha = 1;

  // Draw 4 pine trees from back to front (top-down: canopy circles)
  const trees = [
    { x: 6, y: 6, r: 6 },
    { x: 24, y: 5, r: 5 },
    { x: 16, y: 16, r: 7 },
    { x: 8, y: 24, r: 6 },
    { x: 26, y: 22, r: 5 },
  ];

  for (const t of trees) {
    // Shadow under canopy
    ctx.fillStyle = PAL.forest.shadow;
    ctx.globalAlpha = 0.4;
    ctx.beginPath();
    ctx.arc(t.x + 1, t.y + 1, t.r, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;

    // Trunk (visible at center)
    ctx.fillStyle = PAL.forest.trunk;
    ctx.fillRect(t.x - 1, t.y - 1, 3, 3);

    // Main canopy (dark green)
    ctx.fillStyle = PAL.forest.canopy;
    ctx.beginPath();
    ctx.arc(t.x, t.y, t.r, 0, Math.PI * 2);
    ctx.fill();

    // Canopy highlight (lighter green, offset NW)
    ctx.fillStyle = PAL.forest.light;
    ctx.beginPath();
    ctx.arc(t.x - 1, t.y - 1, t.r * 0.55, 0, Math.PI * 2);
    ctx.fill();

    // Bright highlight spot
    ctx.fillStyle = PAL.forest.highlight;
    ctx.globalAlpha = 0.5;
    ctx.beginPath();
    ctx.arc(t.x - 2, t.y - 2, t.r * 0.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  // Scattered light specks (sunlight through canopy)
  ctx.fillStyle = PAL.forest.highlight;
  ctx.globalAlpha = 0.3;
  for (let i = 0; i < 6; i++) {
    ctx.fillRect(Math.floor(rng() * 30) + 1, Math.floor(rng() * 30) + 1, 1, 1);
  }
  ctx.globalAlpha = 1;

  return c;
}

function drawMountain(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  const rng = seededRandom(55);

  // Deep shadow base
  ctx.fillStyle = PAL.mountain.shadow;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Mountain body (diamond/rhombus from above)
  ctx.fillStyle = PAL.mountain.rock;
  ctx.beginPath();
  ctx.moveTo(16, 1);
  ctx.lineTo(31, 16);
  ctx.lineTo(16, 31);
  ctx.lineTo(1, 16);
  ctx.closePath();
  ctx.fill();

  // NW lit face (lighter)
  ctx.fillStyle = PAL.mountain.light;
  ctx.beginPath();
  ctx.moveTo(16, 1);
  ctx.lineTo(1, 16);
  ctx.lineTo(16, 16);
  ctx.closePath();
  ctx.fill();

  // SE shadow face (darker)
  ctx.fillStyle = PAL.mountain.crevice;
  ctx.globalAlpha = 0.4;
  ctx.beginPath();
  ctx.moveTo(16, 31);
  ctx.lineTo(31, 16);
  ctx.lineTo(16, 16);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;

  // Snow cap (top quadrant)
  ctx.fillStyle = PAL.mountain.snow;
  ctx.beginPath();
  ctx.moveTo(16, 3);
  ctx.lineTo(8, 11);
  ctx.lineTo(16, 11);
  ctx.lineTo(24, 11);
  ctx.closePath();
  ctx.fill();

  // Ice highlight on snow
  ctx.fillStyle = PAL.mountain.ice;
  ctx.globalAlpha = 0.5;
  ctx.beginPath();
  ctx.moveTo(16, 4);
  ctx.lineTo(11, 9);
  ctx.lineTo(16, 9);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;

  // Rocky crevice lines
  ctx.strokeStyle = PAL.mountain.crevice;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.6;
  ctx.beginPath();
  ctx.moveTo(10, 18);
  ctx.lineTo(14, 24);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(20, 14);
  ctx.lineTo(24, 20);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(6, 14);
  ctx.lineTo(10, 12);
  ctx.stroke();
  ctx.globalAlpha = 1;

  // Rocky texture specks
  ctx.fillStyle = PAL.mountain.shadow;
  for (let i = 0; i < 10; i++) {
    const x = 5 + Math.floor(rng() * 22);
    const y = 10 + Math.floor(rng() * 18);
    ctx.fillRect(x, y, 1 + Math.floor(rng() * 2), 1);
  }

  // Light rock specks on lit face
  ctx.fillStyle = PAL.mountain.light;
  ctx.globalAlpha = 0.4;
  for (let i = 0; i < 6; i++) {
    const x = 4 + Math.floor(rng() * 10);
    const y = 6 + Math.floor(rng() * 10);
    ctx.fillRect(x, y, 1, 1);
  }
  ctx.globalAlpha = 1;

  return c;
}

function drawUnknown(): OffscreenCanvas {
  const [c, ctx] = createTileCanvas();
  const rng = seededRandom(77);

  // Deep mystical base
  ctx.fillStyle = PAL.unknown.deep;
  ctx.fillRect(0, 0, TILE_SZ, TILE_SZ);

  // Base gradient effect (radial darkness)
  ctx.fillStyle = PAL.unknown.base;
  ctx.globalAlpha = 0.6;
  ctx.beginPath();
  ctx.arc(16, 16, 14, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;

  // Fog swirl layers
  ctx.strokeStyle = PAL.unknown.mist;
  ctx.lineWidth = 2;
  ctx.globalAlpha = 0.5;
  ctx.beginPath();
  ctx.arc(16, 16, 12, 0.2, 2.5);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(14, 18, 8, 3.2, 5.5);
  ctx.stroke();
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(20, 12, 6, 1.0, 3.8);
  ctx.stroke();
  ctx.globalAlpha = 1;

  // Glowing wisps (lighter purple arcs)
  ctx.strokeStyle = PAL.unknown.glow;
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.6;
  ctx.beginPath();
  ctx.arc(10, 10, 4, 0, 3.5);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(24, 22, 3, 1, 5);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(8, 24, 3, 2, 5.5);
  ctx.stroke();
  ctx.globalAlpha = 1;

  // Sparkle dots
  ctx.fillStyle = PAL.unknown.spark;
  ctx.globalAlpha = 0.7;
  for (let i = 0; i < 8; i++) {
    const x = 3 + Math.floor(rng() * 26);
    const y = 3 + Math.floor(rng() * 26);
    ctx.fillRect(x, y, 1, 1);
  }

  // Larger sparkle dots (brighter)
  ctx.globalAlpha = 0.9;
  ctx.fillRect(12, 8, 1, 1);
  ctx.fillRect(22, 14, 1, 1);
  ctx.fillRect(8, 20, 1, 1);
  ctx.globalAlpha = 1;

  // Ghostly question mark (very subtle)
  ctx.fillStyle = PAL.unknown.spark;
  ctx.font = "bold 16px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.globalAlpha = 0.15;
  ctx.fillText("?", 16, 17);
  ctx.globalAlpha = 1;

  return c;
}

// ---------------------------------------------------------------------------
// Tile cache
// ---------------------------------------------------------------------------

let tileCache: Map<number, OffscreenCanvas> | null = null;

export function initTileCache(): void {
  if (tileCache) return;
  tileCache = new Map<number, OffscreenCanvas>();
  tileCache.set(0,  drawEmpty());
  tileCache.set(1,  drawSettlement());
  tileCache.set(2,  drawPort());
  tileCache.set(3,  drawRuin());
  tileCache.set(4,  drawForest());
  tileCache.set(5,  drawMountain());
  tileCache.set(10, drawOcean());
  tileCache.set(11, drawEmpty());
  tileCache.set(-99, drawUnknown());
}

export function getTile(terrainType: number): OffscreenCanvas {
  if (!tileCache) initTileCache();
  return tileCache!.get(terrainType) ?? tileCache!.get(-99)!;
}

export const TILE_SOURCE_SIZE = TILE_SZ;
export { PAL as TERRAIN_PALETTE };
