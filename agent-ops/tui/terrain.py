"""Terrain grid rendering with colored unicode symbols for textual."""

from __future__ import annotations

from rich.text import Text

# Terrain type -> (char, rich style)
TERRAIN_CHARS: dict[int, tuple[str, str]] = {
    0: ("·", "bright_black"),        # Empty
    1: ("⌂", "bold yellow"),         # Settlement
    2: ("⚓", "bold cyan"),          # Port
    3: ("✦", "bold red"),            # Ruin
    4: ("♠", "green"),               # Forest
    5: ("▲", "bold bright_white"),   # Mountain
    10: ("~", "blue"),               # Ocean
    11: ("·", "bright_black"),       # Plains/Empty
}

TERRAIN_NAMES: dict[int, str] = {
    0: "Empty",
    1: "Settlement",
    2: "Port",
    3: "Ruin",
    4: "Forest",
    5: "Mountain",
    10: "Ocean",
    11: "Plains",
}

# Background colors for richer visual (terrain as block colors)
TERRAIN_BG: dict[int, str] = {
    0: "on #1a1a2e",       # Empty: dark
    1: "on #5c4a1e",       # Settlement: brown bg
    2: "on #1e3a5c",       # Port: dark blue bg
    3: "on #5c1e1e",       # Ruin: dark red bg
    4: "on #1e3a1e",       # Forest: dark green bg
    5: "on #4a4a4a",       # Mountain: gray bg
    10: "on #0a1a3a",      # Ocean: deep blue bg
    11: "on #1a1a2e",      # Plains: dark
}


def render_terrain_rich(grid: list[list[int]], use_bg: bool = True) -> Text:
    """Render full 40x40 grid as Rich Text with colors.

    Each cell gets 2 chars wide for better aspect ratio on terminal.
    """
    text = Text()

    # Column header (every 5th col labeled)
    text.append("   ", style="dim")
    for c in range(len(grid[0]) if grid else 0):
        if c % 5 == 0:
            text.append(f"{c:<2}", style="dim cyan")
        else:
            text.append("  ", style="dim")
    text.append("\n")

    for r, row in enumerate(grid):
        # Row label
        if r % 5 == 0:
            text.append(f"{r:>2} ", style="dim cyan")
        else:
            text.append("   ", style="dim")

        for cell in row:
            char, fg_style = TERRAIN_CHARS.get(cell, ("?", "magenta"))
            if use_bg:
                bg = TERRAIN_BG.get(cell, "")
                style = f"{fg_style} {bg}"
            else:
                style = fg_style
            # 2 chars wide: char + space for better visual
            text.append(f"{char} ", style=style)
        text.append("\n")

    return text


def render_terrain_compact(grid: list[list[int]]) -> Text:
    """Render compact 1-char-wide grid (for smaller spaces)."""
    text = Text()
    for row in grid:
        for cell in row:
            char, style = TERRAIN_CHARS.get(cell, ("?", "magenta"))
            text.append(char, style=style)
        text.append("\n")
    return text


def count_terrain(grid: list[list[int]]) -> dict[str, int]:
    """Count terrain types in a grid."""
    counts: dict[str, int] = {}
    for row in grid:
        for cell in row:
            name = TERRAIN_NAMES.get(cell, "Unknown")
            counts[name] = counts.get(name, 0) + 1
    return counts


def render_legend() -> Text:
    """Render terrain legend as Rich Text."""
    text = Text()
    for tid, (char, style) in sorted(TERRAIN_CHARS.items()):
        if tid == 11:
            continue
        name = TERRAIN_NAMES.get(tid, "?")
        bg = TERRAIN_BG.get(tid, "")
        text.append(f" {char} ", style=f"{style} {bg}")
        text.append(f"{name} ", style="dim")
    return text
