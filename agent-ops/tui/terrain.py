"""Terrain grid rendering matching the reference TUI style.

Reference: dark bg, colored symbols, row numbers both sides,
column headers every 5, 2-char wide cells for readability.
"""

from __future__ import annotations

from rich.text import Text

# Terrain type -> (char, rich style) matching reference screenshot
TERRAIN_CHARS: dict[int, tuple[str, str]] = {
    0: ("·", "bright_black"),          # Empty: dim dot
    1: ("⌂", "bold yellow"),           # Settlement: yellow house
    2: ("⇩", "bold bright_blue"),      # Port: blue down arrow
    3: ("R", "bold red"),              # Ruin: red R
    4: ("▲", "bold green"),            # Forest: green triangle
    5: ("▲", "bright_black"),          # Mountain: gray triangle
    10: ("-", "#2a5a8a"),              # Ocean: blue dash
    11: ("·", "bright_black"),         # Plains/Empty: dim dot
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

# Colors for the count bars in viewport stats
TERRAIN_BAR_COLORS: dict[int, str] = {
    0: "bright_black",
    1: "yellow",
    2: "bright_blue",
    3: "red",
    4: "green",
    5: "bright_black",
    10: "#2a5a8a",
    11: "bright_black",
}


def render_terrain_grid_rich(grid: list[list[int]]) -> Text:
    """Render 40x40 grid as Rich Text matching the reference style.

    Features: row numbers both sides, column numbers every 5,
    2-char wide cells, colored symbols on dark background.
    """
    text = Text()
    rows = len(grid)
    cols = len(grid[0]) if grid else 0

    # Column header
    text.append("    ", style="dim")
    for c in range(cols):
        if c % 5 == 0:
            label = str(c)
            text.append(f"{label:<2}", style="dim cyan")
            # Skip padding chars we already used
        else:
            text.append("  ", style="dim")
    text.append("\n")

    # Grid rows
    for r in range(rows):
        # Left row number
        text.append(f"{r:>3} ", style="dim cyan")

        for c in range(cols):
            cell = grid[r][c]
            char, style = TERRAIN_CHARS.get(cell, ("?", "magenta"))
            text.append(f"{char} ", style=style)

        # Right row number
        text.append(f" {r}", style="dim cyan")
        text.append("\n")

    return text


def render_terrain_legend() -> Text:
    """Render vertical terrain legend matching reference style."""
    text = Text()
    text.append("R ", style="bold cyan")
    text.append("Terrain Legend\n", style="bold")

    entries = [
        (10, "-", "Ocean"),
        (11, "·", "Empty"),
        (2, "⇩", "Port"),
        (1, "⌂", "Settlement"),
        (3, "R", "Ruin"),
        (4, "▲", "Forest"),
        (5, "▲", "Mountain"),
        (-1, "?", "Unknown"),
    ]
    for tid, char, name in entries:
        if tid >= 0:
            _, style = TERRAIN_CHARS.get(tid, ("?", "magenta"))
        else:
            style = "dim magenta"
        text.append(f"  {char}  ", style=style)
        text.append(f"{name}\n", style="")

    return text


def count_terrain(grid: list[list[int]]) -> dict[int, int]:
    """Count terrain types in a grid. Returns {type_id: count}."""
    counts: dict[int, int] = {}
    for row in grid:
        for cell in row:
            counts[cell] = counts.get(cell, 0) + 1
    return counts


def render_viewport_stats(grid: list[list[int]]) -> Text:
    """Render viewport contents with colored count bars (like reference)."""
    text = Text()
    text.append("R ", style="bold cyan")
    text.append("Viewport Contents\n", style="bold")

    counts = count_terrain(grid)
    total = sum(counts.values())

    # Order: Ocean, Empty/Plains, Settlement, Port, Forest, Ruin, Mountain
    display_order = [
        (10, "Ocean"),
        (0, "Empty"),
        (11, "Plains"),
        (1, "Settlement"),
        (2, "Port"),
        (4, "Forest"),
        (3, "Ruin"),
        (5, "Mountain"),
    ]

    max_bar = 20  # max bar width in chars
    max_count = max(counts.values()) if counts else 1

    for tid, name in display_order:
        c = counts.get(tid, 0)
        if c == 0 and tid in (0, 11):
            # Skip empty types that have 0 count (plains/empty overlap)
            if tid == 0 and counts.get(11, 0) > 0:
                continue
            if tid == 11 and counts.get(0, 0) > 0:
                continue

        char, style = TERRAIN_CHARS.get(tid, ("?", "dim"))
        bar_color = TERRAIN_BAR_COLORS.get(tid, "white")
        bar_len = int((c / max_count) * max_bar) if max_count > 0 else 0

        text.append(f"  {char} ", style=style)
        text.append(f"{name:<12}", style="")
        text.append(f"{c:>4} ", style="bold")
        text.append("█" * bar_len, style=bar_color)
        text.append("\n")

    # Coverage
    observed = total
    text.append(f"\n  Observed: {observed}/{total} (100%)\n", style="dim")

    return text


def render_settlement_stats(grid: list[list[int]]) -> Text:
    """Count settlements and show stats."""
    text = Text()
    counts = count_terrain(grid)
    settlements = counts.get(1, 0)
    ports = counts.get(2, 0)
    ruins = counts.get(3, 0)

    text.append("⌂ ", style="bold yellow")
    text.append(f"Settlements: {settlements} ({settlements} alive)\n", style="")
    if ports:
        text.append("⇩ ", style="bold bright_blue")
        text.append(f"Ports: {ports}\n", style="")
    if ruins:
        text.append("R ", style="bold red")
        text.append(f"Ruins: {ruins}\n", style="")

    return text
