"""
File Name: theme.py

Author: Jonathan W (web port written with Claude)
Date Created: 11/19/2026
Last Update: 11/19/2026
Version: 2.1.0-web

Scope: Web version of theme.py with no Qt. Same Theme dataclass, THEMES, current(), set_theme() and matplotlib
    styling as the desktop app, so Daily_Graph.py and Hourly_Graph.py run unchanged. heat_color() returns a hex
    string instead of a QColor.
"""

import colorsys
from dataclasses import dataclass

import matplotlib
from matplotlib import font_manager

# ===== THEME DEFINITION =====
@dataclass(frozen=True)
class Theme:
    """One complete set of UI and chart colors.

    Attributes:
        name: Display name shown in the View > Theme menu.
        window: Main background, also the chart background.
        surface: Cards and chart plot areas.
        border: Card borders, chart spines and gridlines.
        text: Primary text.
        muted: Secondary text and tick labels.
        accent: Highlights and selections.
        hot: Highs and temperature lines.
        cool: Lows.
        precip: Precipitation bars.
        sunrise: Sunrise marker line.
        sunset: Sunset marker line.
        highlighted_text: Text drawn on top of the accent color.
    """

    name: str
    window: str
    surface: str
    border: str
    text: str
    muted: str
    accent: str
    hot: str
    cool: str
    precip: str
    sunrise: str
    sunset: str
    highlighted_text: str


THEMES: dict[str, Theme] = {
    theme.name: theme
    for theme in (
        Theme(
            name="Midnight",  # The original dark theme
            window="#1b1d23", surface="#252832", border="#343846", text="#e6e6eb", muted="#9aa0ae",
            accent="#ff7a45", hot="#ff6b5b", cool="#5aa9ff", precip="#4f8fe0", sunrise="#f5b041",
            sunset="#b48cff", highlighted_text="#1b1d23",
        ),
        Theme(
            name="Heatwave",  # Warm ember browns, for the Too Damn Hot! mood
            window="#1f1512", surface="#2b1d18", border="#45302a", text="#f4e6dc", muted="#b89c8c",
            accent="#ff8a3d", hot="#ff5a3c", cool="#6fb7c9", precip="#5f9fd6", sunrise="#ffc247",
            sunset="#d97ab0", highlighted_text="#1f1512",
        ),
        Theme(
            name="Overcast",  # Softer, lower-contrast cool grays
            window="#262b30", surface="#30363d", border="#424a53", text="#dfe5ea", muted="#9aa5b1",
            accent="#7cc4e0", hot="#f08a6c", cool="#7fb2f0", precip="#6aa8d8", sunrise="#e8c170",
            sunset="#b9a3e3", highlighted_text="#262b30",
        ),
        Theme(
            name="Daylight",  # Light theme; data colors are darkened so they stay readable on white
            window="#eef1f5", surface="#ffffff", border="#d3d8e0", text="#1f2430", muted="#5f6776",
            accent="#e0602a", hot="#d6453a", cool="#2f74d0", precip="#3b82c4", sunrise="#c98a00",
            sunset="#7a4fd0", highlighted_text="#ffffff",
        ),
        Theme(
            name="Cunty Purple",  # Deep plum with a loud orchid accent. Serving.
            window="#1c1424", surface="#271b33", border="#3d2b4d", text="#f3e8f8", muted="#b7a0c8",
            accent="#d26bff", hot="#ff6b9a", cool="#7fb8ff", precip="#6f9fe8", sunrise="#ffc247",
            sunset="#e48cff", highlighted_text="#1c1424",
        ),
    )
}
DEFAULT_THEME = "Midnight"

# Matches the Calibri used by the Qt labels. Picked up front because matplotlib warns about every missing family.
_INSTALLED_FONTS = {font.name for font in font_manager.fontManager.ttflist}
FONT_FAMILY = next((name for name in ("Calibri", "Segoe UI") if name in _INSTALLED_FONTS), "DejaVu Sans")

# Holds the active theme. A dict avoids a `global` statement, which Ruff flags (PLW0603).
_state: dict[str, Theme] = {"theme": THEMES[DEFAULT_THEME]}



# ===== HEAT SCALE =====
def heat_color(temp_f: float) -> str:
    """Maps a temperature to a blue-to-red hex color, used for the hourly bars and 10-day highs.

    The scale is fixed in °F (40°F is cool blue, 105°F+ is red) so colors don't shift when the display switches
    to Celsius.

    Args:
        temp_f: Temperature in °F.

    Returns:
        A hex color such as "#f5a742".
    """
    t = max(0.0, min(1.0, (temp_f - 40) / 65))
    red, green, blue = colorsys.hsv_to_rgb((200 - t * 195) / 360, 0.62, 0.96)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


# ===== PUBLIC API =====
def current() -> Theme:
    """Returns the active theme.

    Graph code should call this at draw time rather than importing colors at module level.

    Returns:
        The Theme currently applied.
    """
    return _state["theme"]


def set_theme(name: str) -> Theme:
    """Makes a theme active and applies it to matplotlib.

    Args:
        name: Key from THEMES. An unknown name falls back to DEFAULT_THEME.

    Returns:
        The Theme that was applied.
    """
    theme = THEMES.get(name, THEMES[DEFAULT_THEME])
    _state["theme"] = theme
    _apply_matplotlib(theme)
    return theme


# ===== MATPLOTLIB =====
def _apply_matplotlib(theme: Theme) -> None:
    """Points matplotlib's defaults at a theme. Affects figures and axes created after the call.

    Args:
        theme: The theme to take colors from.
    """
    matplotlib.rcParams.update({
        "figure.facecolor": theme.window,
        "savefig.facecolor": theme.window,
        "axes.facecolor": theme.surface,
        "axes.edgecolor": theme.border,
        "axes.labelcolor": theme.muted,
        "axes.titlecolor": theme.text,
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": theme.border,
        "grid.linewidth": 0.8,
        "text.color": theme.text,
        "xtick.color": theme.muted,
        "ytick.color": theme.muted,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.labelcolor": theme.text,
        "legend.fontsize": 9,
        "font.family": FONT_FAMILY,
    })


set_theme(DEFAULT_THEME)  # Standalone graph scripts get a styled chart without any Qt setup
