"""Shared visual language for the app: colors, type scale, and a couple of
small widget factories. Centralizing these keeps every tab looking like part
of the same product instead of five independently-styled screens.

Colors that need different values per appearance mode are (light, dark)
tuples, as customtkinter expects. Saturated accent/status colors are single
hex values — they read fine against both light and dark surfaces.
"""
import customtkinter as ctk

# ---------------------------------------------------------------- typography
FONT_FAMILY = "Segoe UI"

FONT_TITLE = (FONT_FAMILY, 21, "bold")        # app name, header bar
FONT_SUBTITLE = (FONT_FAMILY, 12)             # header tagline
FONT_H1 = (FONT_FAMILY, 15, "bold")           # section headers within a tab
FONT_H2 = (FONT_FAMILY, 13, "bold")           # card titles / field group labels
FONT_BODY = (FONT_FAMILY, 12)
FONT_BODY_BOLD = (FONT_FAMILY, 12, "bold")
FONT_SMALL = (FONT_FAMILY, 11)
FONT_SMALL_BOLD = (FONT_FAMILY, 11, "bold")
FONT_MONO = ("Consolas", 11)

# -------------------------------------------------------------------- colors
ACCENT = "#3B82F6"
ACCENT_HOVER = "#2563EB"

SUCCESS = "#22C55E"
SUCCESS_HOVER = "#16A34A"

DANGER = "#EF4444"
DANGER_HOVER = "#DC2626"

WARNING = "#F59E0B"
WARNING_HOVER = "#D97706"

GOOGLE_BLUE = "#4285F4"
GOOGLE_BLUE_HOVER = "#3367D6"

NEUTRAL = ("#D8DEE8", "#4B5259")
NEUTRAL_HOVER = ("#C3CBD8", "#3A3F45")

TEXT_MUTED = ("#5B6472", "#9AA5B1")

SURFACE = ("#FFFFFF", "#242830")
SURFACE_ALT = ("#F3F5F8", "#1C1F24")
BORDER = ("#E2E6EC", "#33383F")

HEADER_BG = ("#1F2937", "#161A20")
HEADER_TEXT = "#F3F5F8"
HEADER_SUBTEXT = ("#CBD5E1", "#8B94A1")

# -------------------------------------------------------------------- layout
RADIUS = 10
RADIUS_SM = 8
RADIUS_PILL = 12
PAD = 12

_BADGE_COLORS = {
    "success": (SUCCESS, "#FFFFFF"),
    "danger": (DANGER, "#FFFFFF"),
    "warning": (WARNING, "#1F2937"),
    "info": (ACCENT, "#FFFFFF"),
    "neutral": (NEUTRAL, ("#374151", "#E5E7EB")),
}


def card(parent, **kwargs):
    """A CTkFrame styled as a raised card: subtle border + rounded corners."""
    options = dict(fg_color=SURFACE, corner_radius=RADIUS, border_width=1, border_color=BORDER)
    options.update(kwargs)
    return ctk.CTkFrame(parent, **options)


def section_label(parent, text, **kwargs):
    """A bold section heading, used to title a card or panel."""
    options = dict(font=FONT_H1, text_color=("#111827", "#F3F5F8"))
    options.update(kwargs)
    return ctk.CTkLabel(parent, text=text, **options)


def badge(parent, text, kind="neutral"):
    """A small rounded status pill (e.g. 'Running', 'Authenticated', 'Failed')."""
    fg, fg_text = _BADGE_COLORS.get(kind, _BADGE_COLORS["neutral"])
    return ctk.CTkLabel(
        parent,
        text=text,
        font=FONT_SMALL_BOLD,
        fg_color=fg,
        text_color=fg_text,
        corner_radius=RADIUS_PILL,
        padx=10,
        pady=3,
    )


def set_badge(label, text, kind="neutral"):
    """Update an existing badge label in place (text + color)."""
    fg, fg_text = _BADGE_COLORS.get(kind, _BADGE_COLORS["neutral"])
    label.configure(text=text, fg_color=fg, text_color=fg_text)


def primary_button(parent, **kwargs):
    options = dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=RADIUS_SM,
                   font=FONT_BODY_BOLD)
    options.update(kwargs)
    return ctk.CTkButton(parent, **options)


def danger_button(parent, **kwargs):
    options = dict(fg_color=DANGER, hover_color=DANGER_HOVER, corner_radius=RADIUS_SM,
                   font=FONT_BODY_BOLD)
    options.update(kwargs)
    return ctk.CTkButton(parent, **options)


def secondary_button(parent, **kwargs):
    options = dict(fg_color=NEUTRAL, hover_color=NEUTRAL_HOVER, corner_radius=RADIUS_SM,
                   font=FONT_BODY_BOLD, text_color=("#111827", "#F3F5F8"))
    options.update(kwargs)
    return ctk.CTkButton(parent, **options)
