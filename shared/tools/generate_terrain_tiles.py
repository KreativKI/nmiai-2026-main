#!/usr/bin/env python3
"""
Generate 32x32 SVG terrain tile sprites for the Astar Island dashboard.

Produces 8 SVG files (one per terrain type) using simple geometric shapes
in a muted Norse-fantasy palette.  These serve as reference assets; the
dashboard canvas renderer draws its own tiles via OffscreenCanvas for
maximum performance.

Usage:
    python3 generate_terrain_tiles.py

Output directory:
    agent-ops/dashboard/public/assets/terrain/
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "agent-ops" / "dashboard" / "public" / "assets" / "terrain"
SZ = 32  # tile size in px

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
PAL = dict(
    ocean_deep="#143d6e", ocean_mid="#1a4b8c", ocean_light="#2d6cb5", ocean_foam="#5a9ad6",
    empty_base="#c4a882", empty_dark="#a8906a", empty_speck="#8a7456",
    settle_wall="#8b6914", settle_roof="#b84c3c", settle_ground="#a0937d", settle_window="#f2c94c",
    port_water="#1a4b8c", port_plank="#6b4423", port_rope="#a0845c", port_post="#4a3218",
    ruin_stone="#5a5a5a", ruin_light="#8a8a8a", ruin_moss="#4a6a4a", ruin_shadow="#3a3a3a",
    forest_canopy="#1a5c2a", forest_light="#2d8a3f", forest_trunk="#5c3a1e", forest_floor="#2a4a20",
    mtn_rock="#6a6a6a", mtn_light="#9a9a9a", mtn_snow="#d8d8e8", mtn_shadow="#4a4a5a",
    unk_mist="#5a3d7a", unk_glow="#8a6aaa", unk_dark="#3a2a5a", unk_spark="#b89ae0",
)


def svg_wrap(inner: str) -> str:
    """Wrap SVG content in the standard 32x32 SVG element."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SZ}" height="{SZ}" '
        f'viewBox="0 0 {SZ} {SZ}" shape-rendering="crispEdges">\n{inner}</svg>\n'
    )


def rect(x: int, y: int, w: int, h: int, fill: str) -> str:
    return f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'


def circle(cx: float, cy: float, r: float, fill: str, opacity: float = 1.0) -> str:
    op = f' opacity="{opacity}"' if opacity < 1 else ""
    return f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{op}/>'


def line(x1: int, y1: int, x2: int, y2: int, stroke: str, width: float = 1) -> str:
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{width}"/>'


def polygon(points: list[tuple[int, int]], fill: str) -> str:
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'  <polygon points="{pts}" fill="{fill}"/>'


def path_d(d: str, stroke: str, fill: str = "none", width: float = 1) -> str:
    return f'  <path d="{d}" stroke="{stroke}" fill="{fill}" stroke-width="{width}"/>'


# ---------------------------------------------------------------------------
# Tile generators
# ---------------------------------------------------------------------------

def ocean_svg() -> str:
    parts = [
        rect(0, 0, SZ, SZ, PAL["ocean_deep"]),
        rect(0, 8, SZ, 6, PAL["ocean_mid"]),
        rect(0, 22, SZ, 6, PAL["ocean_mid"]),
    ]
    # Wave curves
    for row in range(4):
        y = 4 + row * 8
        parts.append(path_d(
            f"M0 {y} Q8 {y - 2} 16 {y} Q24 {y + 2} 32 {y}",
            PAL["ocean_light"],
        ))
    # Foam specks
    import random
    rng = random.Random(42)
    for _ in range(6):
        x, y = rng.randint(0, 29), rng.randint(0, 29)
        parts.append(rect(x, y, 2, 1, PAL["ocean_foam"]))
    return svg_wrap("\n".join(parts))


def empty_svg() -> str:
    parts = [rect(0, 0, SZ, SZ, PAL["empty_base"])]
    import random
    rng = random.Random(7)
    for _ in range(8):
        x, y = rng.randint(0, 27), rng.randint(0, 27)
        w, h = 3 + rng.randint(0, 3), 2 + rng.randint(0, 2)
        parts.append(rect(x, y, w, h, PAL["empty_dark"]))
    for _ in range(12):
        parts.append(rect(rng.randint(0, 30), rng.randint(0, 30), 1, 1, PAL["empty_speck"]))
    return svg_wrap("\n".join(parts))


def settlement_svg() -> str:
    parts = [
        rect(0, 0, SZ, SZ, PAL["settle_ground"]),
        # House body
        rect(6, 8, 20, 16, PAL["settle_wall"]),
        # Roof edges
        rect(6, 8, 20, 3, PAL["settle_roof"]),
        rect(6, 21, 20, 3, PAL["settle_roof"]),
        # Roof ridge
        line(16, 6, 16, 26, PAL["settle_roof"], 2),
        # Windows
        rect(11, 14, 2, 2, PAL["settle_window"]),
        rect(19, 14, 2, 2, PAL["settle_window"]),
        # Door
        rect(14, 18, 4, 4, "#5a4010"),
        # Path
        rect(13, 24, 6, 8, PAL["empty_dark"]),
    ]
    return svg_wrap("\n".join(parts))


def port_svg() -> str:
    parts = [
        rect(0, 0, SZ, SZ, PAL["port_water"]),
    ]
    # Wave lines
    for row in range(4):
        y = 4 + row * 8
        parts.append(path_d(f"M0 {y} Q4 {y - 1} 8 {y}", PAL["ocean_light"]))
    # Dock
    parts.append(rect(14, 0, 18, SZ, PAL["port_plank"]))
    # Plank lines
    for y in range(0, SZ, 4):
        parts.append(line(14, y, 32, y, PAL["port_post"]))
    # Posts
    for y in [2, 14, 26]:
        parts.append(rect(13, y, 3, 4, PAL["port_post"]))
    # Rope coil
    parts.append(
        f'  <circle cx="24" cy="16" r="3" fill="none" stroke="{PAL["port_rope"]}" stroke-width="1"/>'
    )
    return svg_wrap("\n".join(parts))


def ruin_svg() -> str:
    parts = [
        rect(0, 0, SZ, SZ, PAL["empty_dark"]),
        # Wall fragments
        rect(3, 18, 12, 3, PAL["ruin_stone"]),
        rect(3, 10, 3, 11, PAL["ruin_stone"]),
        rect(18, 4, 10, 3, PAL["ruin_stone"]),
        rect(25, 4, 3, 10, PAL["ruin_stone"]),
    ]
    # Rubble
    import random
    rng = random.Random(13)
    for _ in range(8):
        x, y = rng.randint(2, 29), rng.randint(2, 29)
        s = 1 + rng.randint(0, 2)
        parts.append(rect(x, y, s, s, PAL["ruin_light"]))
    # Moss
    parts += [
        rect(5, 12, 2, 2, PAL["ruin_moss"]),
        rect(20, 8, 3, 2, PAL["ruin_moss"]),
        rect(10, 22, 2, 2, PAL["ruin_moss"]),
    ]
    # Shadows
    parts += [
        rect(4, 21, 10, 1, PAL["ruin_shadow"]),
        rect(19, 7, 8, 1, PAL["ruin_shadow"]),
    ]
    return svg_wrap("\n".join(parts))


def forest_svg() -> str:
    parts = [rect(0, 0, SZ, SZ, PAL["forest_floor"])]
    trees = [(8, 7, 7), (24, 10, 6), (14, 22, 8)]
    for tx, ty, r in trees:
        parts.append(rect(tx - 1, ty - 1, 3, 3, PAL["forest_trunk"]))
        parts.append(circle(tx, ty, r, PAL["forest_canopy"]))
        parts.append(circle(tx - 1, ty - 1, r * 0.5, PAL["forest_light"]))
    # Undergrowth
    import random
    rng = random.Random(99)
    for _ in range(6):
        parts.append(rect(rng.randint(0, 29), rng.randint(0, 29), 2, 1, PAL["forest_light"]))
    return svg_wrap("\n".join(parts))


def mountain_svg() -> str:
    parts = [
        rect(0, 0, SZ, SZ, PAL["mtn_shadow"]),
        # Diamond shape (top-down mountain)
        polygon([(16, 2), (30, 16), (16, 30), (2, 16)], PAL["mtn_rock"]),
        # Lighter NW face
        polygon([(16, 2), (2, 16), (16, 16)], PAL["mtn_light"]),
        # Snow cap
        polygon([(16, 4), (10, 12), (22, 12)], PAL["mtn_snow"]),
    ]
    # Rocky texture
    import random
    rng = random.Random(55)
    for _ in range(8):
        x = 6 + rng.randint(0, 19)
        y = 12 + rng.randint(0, 15)
        parts.append(rect(x, y, 2, 1, PAL["mtn_shadow"]))
    return svg_wrap("\n".join(parts))


def unknown_svg() -> str:
    parts = [
        rect(0, 0, SZ, SZ, PAL["unk_dark"]),
        # Fog swirl arcs
        path_d("M22 8 A12 12 0 0 1 8 22", PAL["unk_mist"], width=2),
        path_d("M10 24 A8 8 0 0 1 24 10", PAL["unk_glow"]),
        # Wisp circles
        f'  <circle cx="10" cy="10" r="4" fill="none" stroke="{PAL["unk_glow"]}" stroke-width="1"/>',
        f'  <circle cx="24" cy="22" r="3" fill="none" stroke="{PAL["unk_glow"]}" stroke-width="1"/>',
    ]
    # Sparkles
    import random
    rng = random.Random(77)
    for _ in range(5):
        x, y = 4 + rng.randint(0, 23), 4 + rng.randint(0, 23)
        parts.append(rect(x, y, 1, 1, PAL["unk_spark"]))
    # Question mark
    parts.append(
        f'  <text x="16" y="20" font-size="14" font-weight="bold" font-family="monospace" '
        f'text-anchor="middle" fill="{PAL["unk_spark"]}" opacity="0.3">?</text>'
    )
    return svg_wrap("\n".join(parts))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TILES = {
    "ocean":      ocean_svg,
    "empty":      empty_svg,
    "settlement": settlement_svg,
    "port":       port_svg,
    "ruin":       ruin_svg,
    "forest":     forest_svg,
    "mountain":   mountain_svg,
    "unknown":    unknown_svg,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, gen in TILES.items():
        path = OUT_DIR / f"{name}.svg"
        path.write_text(gen())
        print(f"  wrote {path.relative_to(OUT_DIR.parent.parent.parent.parent)}")
    print(f"\nDone: {len(TILES)} terrain tiles in {OUT_DIR}")


if __name__ == "__main__":
    main()
