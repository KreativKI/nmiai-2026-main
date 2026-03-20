"""Terrain grid rendering with single-char unicode symbols."""

from __future__ import annotations

from rich.text import Text

# Terrain type -> (char, rich color)
TERRAIN_CHARS: dict[int, tuple[str, str]] = {
    0: ("·", "bright_black"),       # Empty
    1: ("⌂", "yellow"),             # Settlement
    2: ("⚓", "cyan"),              # Port
    3: ("✦", "red"),                # Ruin
    4: ("♠", "green"),              # Forest
    5: ("▲", "bright_white"),       # Mountain
    10: ("~", "blue"),              # Ocean
    11: ("·", "bright_black"),      # Plains/Empty
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


def render_terrain_row(row: list[int]) -> Text:
    """Render a single row of terrain as a Rich Text object."""
    text = Text()
    for cell in row:
        char, color = TERRAIN_CHARS.get(cell, ("?", "magenta"))
        text.append(char, style=color)
    return text


def render_terrain_grid(grid: list[list[int]]) -> str:
    """Render full 40x40 grid as plain string (for Static widget)."""
    lines = []
    for row in grid:
        line = ""
        for cell in row:
            char, _ = TERRAIN_CHARS.get(cell, ("?", "magenta"))
            line += char
        lines.append(line)
    return "\n".join(lines)


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
    for tid, (char, color) in sorted(TERRAIN_CHARS.items()):
        if tid == 11:
            continue  # Skip plains (same as empty)
        name = TERRAIN_NAMES.get(tid, "?")
        text.append(f" {char}", style=color)
        text.append(f" {name} ", style="dim")
    return text
