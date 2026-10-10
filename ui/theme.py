"""Shared visual language for the app: a strictly grayscale palette, the type
scale, and small widget factories. Centralizing these keeps every page
looking like part of the same product.

Design rules this module encodes:
  * No hue anywhere. Hierarchy comes from lightness alone.
  * One bright thing per screen: the primary action is an inverted (ink)
    button, so the eye lands on "what to do next" first.
  * Status is carried by a glyph + word (✓ Ready, ● Running, ! Warning,
    ✕ Failed), never by color, so it reads the same in both modes.

Colors are (light, dark) tuples, as customtkinter expects.
"""
import tkinter.font as tkfont
import customtkinter as ctk

# -------------------------------------------------------------------- colors
CANVAS = ("#F2F2F2", "#141414")        # window background
PANEL = ("#FFFFFF", "#1C1C1C")         # cards, sidebar
RAISED = ("#EBEBEB", "#262626")        # inputs, list rows, secondary buttons
RAISED_HOVER = ("#DEDEDE", "#303030")
LINE = ("#D9D9D9", "#2E2E2E")          # hairline borders
LINE_STRONG = ("#B5B5B5", "#474747")   # outlined buttons, focus-ish edges

INK = ("#141414", "#F2F2F2")           # primary text + primary action fill
INK_HOVER = ("#000000", "#FFFFFF")
ON_INK = ("#FFFFFF", "#141414")        # text sitting on an ink fill
TEXT_MUTED = ("#5E5E5E", "#9E9E9E")
TEXT_FAINT = ("#8A8A8A", "#6E6E6E")

# Legacy names still referenced by a few call sites.
SURFACE = PANEL
SURFACE_ALT = RAISED
BORDER = LINE
NEUTRAL = RAISED
NEUTRAL_HOVER = RAISED_HOVER
ACCENT = INK
ACCENT_HOVER = INK_HOVER

# ---------------------------------------------------------------- typography
# Families are resolved against what's installed in load_fonts(); these are
# the Windows 11 faces we want, with safe fallbacks.
_DISPLAY_CANDIDATES = ("Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI")
_TEXT_CANDIDATES = ("Segoe UI Variable Text", "Segoe UI")
_MONO_CANDIDATES = ("Cascadia Mono", "Consolas", "Courier New")

FONT_FAMILY = "Segoe UI"
FONT_DISPLAY_FAMILY = "Segoe UI"
FONT_MONO_FAMILY = "Consolas"


def _build_fonts():
    """(Re)build the font tuples from the resolved families. Sizes are px."""
    global FONT_PAGE_TITLE, FONT_WORDMARK, FONT_H1, FONT_H2, FONT_BODY, FONT_BODY_BOLD
    global FONT_SMALL, FONT_SMALL_BOLD, FONT_MONO, FONT_NAV, FONT_TITLE, FONT_SUBTITLE
    FONT_PAGE_TITLE = (FONT_DISPLAY_FAMILY, 26, "bold")    # page heading
    FONT_WORDMARK = (FONT_DISPLAY_FAMILY, 18, "bold")      # sidebar app name
    FONT_H1 = (FONT_DISPLAY_FAMILY, 17, "bold")            # card titles
    FONT_H2 = (FONT_FAMILY, 14, "bold")                    # row titles, sub-sections
    FONT_BODY = (FONT_FAMILY, 13)
    FONT_BODY_BOLD = (FONT_FAMILY, 13, "bold")
    FONT_NAV = (FONT_FAMILY, 14)
    FONT_SMALL = (FONT_FAMILY, 12)
    FONT_SMALL_BOLD = (FONT_FAMILY, 12, "bold")
    FONT_MONO = (FONT_MONO_FAMILY, 12)
    FONT_TITLE = FONT_WORDMARK
    FONT_SUBTITLE = FONT_SMALL


_build_fonts()


def load_fonts(root):
    """Pick the best installed families. Call once, after the Tk root exists
    and before any widget is built."""
    global FONT_FAMILY, FONT_DISPLAY_FAMILY, FONT_MONO_FAMILY
    installed = set(tkfont.families(root))

    def pick(candidates):
        return next((f for f in candidates if f in installed), candidates[-1])

    FONT_FAMILY = pick(_TEXT_CANDIDATES)
    FONT_DISPLAY_FAMILY = pick(_DISPLAY_CANDIDATES)
    FONT_MONO_FAMILY = pick(_MONO_CANDIDATES)
    _build_fonts()

    # Widgets created without an explicit font (dropdown menus, dialogs)
    # fall back to the theme's CTkFont entry.
    # (ThemeManager has already collapsed it to the current platform's entry.)
    ctk.ThemeManager.theme["CTkFont"].update(family=FONT_FAMILY, size=13)


# -------------------------------------------------------------------- layout
RADIUS = 12
RADIUS_SM = 8
RADIUS_PILL = 11
PAD = 20          # inner padding of a card
GAP = 12          # space between sibling cards
CONTROL_H = 34    # height of buttons / inputs / menus


def apply_ctk_theme():
    """Recolor customtkinter's built-in theme so every widget — including ones
    we don't style explicitly (scrollbars, dropdown menus, dialogs) — lands in
    the grayscale palette. Call before creating the root window."""
    t = ctk.ThemeManager.theme
    t["CTk"]["fg_color"] = list(CANVAS)
    t["CTkToplevel"]["fg_color"] = list(CANVAS)
    t["CTkFrame"].update(fg_color=list(PANEL), top_fg_color=list(RAISED),
                         border_color=list(LINE), corner_radius=RADIUS)
    t["CTkButton"].update(fg_color=list(RAISED), hover_color=list(RAISED_HOVER),
                          border_color=list(LINE_STRONG), text_color=list(INK),
                          text_color_disabled=list(TEXT_FAINT), corner_radius=RADIUS_SM)
    t["CTkLabel"]["text_color"] = list(INK)
    t["CTkEntry"].update(fg_color=list(RAISED), border_color=list(LINE), border_width=1,
                         text_color=list(INK), placeholder_text_color=list(TEXT_FAINT),
                         corner_radius=RADIUS_SM)
    for key in ("CTkCheckBox", "CTkRadioButton"):
        t[key].update(fg_color=list(INK), hover_color=list(INK_HOVER),
                      border_color=list(LINE_STRONG), text_color=list(INK),
                      text_color_disabled=list(TEXT_FAINT))
    t["CTkCheckBox"]["checkmark_color"] = list(ON_INK)
    t["CTkSwitch"].update(fg_color=list(LINE_STRONG), progress_color=list(INK),
                          button_color=list(("#FFFFFF", "#8A8A8A")),
                          button_hover_color=list(("#FFFFFF", "#A8A8A8")),
                          text_color=list(INK), text_color_disabled=list(TEXT_FAINT))
    t["CTkProgressBar"].update(fg_color=list(RAISED), progress_color=list(INK))
    t["CTkSlider"].update(fg_color=list(RAISED), progress_color=list(INK),
                          button_color=list(INK), button_hover_color=list(INK_HOVER))
    t["CTkOptionMenu"].update(fg_color=list(RAISED), button_color=list(RAISED),
                              button_hover_color=list(RAISED_HOVER), text_color=list(INK),
                              text_color_disabled=list(TEXT_FAINT), corner_radius=RADIUS_SM)
    t["CTkComboBox"].update(fg_color=list(RAISED), border_color=list(LINE),
                            button_color=list(LINE), button_hover_color=list(LINE_STRONG),
                            text_color=list(INK))
    t["CTkScrollbar"].update(button_color=list(LINE), button_hover_color=list(LINE_STRONG))
    # Selected segment is mid-gray, not ink: one text color serves every segment.
    t["CTkSegmentedButton"].update(fg_color=list(RAISED), selected_color=list(LINE_STRONG),
                                   selected_hover_color=list(LINE_STRONG),
                                   unselected_color=list(RAISED),
                                   unselected_hover_color=list(RAISED_HOVER),
                                   text_color=list(INK), border_width=3,
                                   text_color_disabled=list(TEXT_FAINT))
    t["CTkTextbox"].update(fg_color=list(CANVAS), border_color=list(LINE),
                           text_color=list(INK), scrollbar_button_color=list(LINE),
                           scrollbar_button_hover_color=list(LINE_STRONG))
    t["CTkScrollableFrame"]["label_fg_color"] = list(PANEL)
    t["DropdownMenu"].update(fg_color=list(RAISED), hover_color=list(RAISED_HOVER),
                             text_color=list(INK))


# -------------------------------------------------------------- status pills
# Each kind: (fill, text color, glyph). Hierarchy by lightness only.
_BADGE_STYLES = {
    "info": (INK, ON_INK, "●"),                 # running / active: the loudest
    "success": (RAISED, INK, "✓"),
    "warning": (RAISED, INK, "!"),
    "danger": (LINE_STRONG, INK, "✕"),
    "neutral": (RAISED, TEXT_MUTED, ""),
}


def _badge_text(text, kind):
    glyph = _BADGE_STYLES.get(kind, _BADGE_STYLES["neutral"])[2]
    return f"{glyph}  {text}" if glyph and text not in ("", "-") else text


def badge(parent, text, kind="neutral"):
    """A small rounded status pill (e.g. '✓ Ready', '● Running')."""
    fg, fg_text, _ = _BADGE_STYLES.get(kind, _BADGE_STYLES["neutral"])
    return ctk.CTkLabel(
        parent, text=_badge_text(text, kind), font=FONT_SMALL_BOLD,
        fg_color=fg, text_color=fg_text, corner_radius=RADIUS_PILL,
        padx=10, pady=2, height=24,
    )


def set_badge(label, text, kind="neutral"):
    """Update an existing badge label in place (text + style)."""
    fg, fg_text, _ = _BADGE_STYLES.get(kind, _BADGE_STYLES["neutral"])
    label.configure(text=_badge_text(text, kind), fg_color=fg, text_color=fg_text)


# ------------------------------------------------------------------ builders
def card(parent, **kwargs):
    """A panel on the canvas: flat fill, hairline border, rounded corners."""
    options = dict(fg_color=PANEL, corner_radius=RADIUS, border_width=1, border_color=LINE)
    options.update(kwargs)
    return ctk.CTkFrame(parent, **options)


def section_label(parent, text, **kwargs):
    """A card title."""
    options = dict(font=FONT_H1, text_color=INK, anchor="w")
    options.update(kwargs)
    return ctk.CTkLabel(parent, text=text, **options)


def hint_label(parent, text, **kwargs):
    """Muted helper text that explains a control or an empty state."""
    options = dict(font=FONT_SMALL, text_color=TEXT_MUTED, anchor="w", justify="left")
    options.update(kwargs)
    return ctk.CTkLabel(parent, text=text, **options)


def field_label(parent, text, **kwargs):
    """Label that sits directly above a form input."""
    options = dict(font=FONT_SMALL_BOLD, text_color=TEXT_MUTED, anchor="w")
    options.update(kwargs)
    return ctk.CTkLabel(parent, text=text, **options)


def entry(parent, **kwargs):
    options = dict(font=FONT_BODY, height=CONTROL_H, corner_radius=RADIUS_SM,
                   fg_color=RAISED, border_color=LINE, border_width=1)
    options.update(kwargs)
    return ctk.CTkEntry(parent, **options)


def option_menu(parent, **kwargs):
    options = dict(font=FONT_BODY, height=CONTROL_H, corner_radius=RADIUS_SM,
                   fg_color=RAISED, button_color=RAISED, button_hover_color=RAISED_HOVER,
                   text_color=INK, dropdown_font=FONT_BODY, dynamic_resizing=False)
    options.update(kwargs)
    return ctk.CTkOptionMenu(parent, **options)


def primary_button(parent, **kwargs):
    """The one bright action on a screen."""
    options = dict(fg_color=INK, hover_color=INK_HOVER, text_color=ON_INK,
                   text_color_disabled=TEXT_FAINT, corner_radius=RADIUS_SM,
                   font=FONT_BODY_BOLD, height=CONTROL_H)
    options.update(kwargs)
    button = ctk.CTkButton(parent, **options)
    button._is_primary = True
    set_enabled(button, options.get("state", "normal") != "disabled")
    return button


def secondary_button(parent, **kwargs):
    options = dict(fg_color=RAISED, hover_color=RAISED_HOVER, text_color=INK,
                   text_color_disabled=TEXT_FAINT, corner_radius=RADIUS_SM,
                   font=FONT_BODY_BOLD, height=CONTROL_H)
    options.update(kwargs)
    return ctk.CTkButton(parent, **options)


def danger_button(parent, **kwargs):
    """Destructive actions are outlined, never filled: present, but quiet.
    Every one of them is also guarded by a confirmation dialog."""
    options = dict(fg_color="transparent", hover_color=RAISED, text_color=INK,
                   text_color_disabled=TEXT_FAINT, border_width=1,
                   border_color=LINE_STRONG, corner_radius=RADIUS_SM,
                   font=FONT_BODY_BOLD, height=CONTROL_H)
    options.update(kwargs)
    return ctk.CTkButton(parent, **options)


class ProgressBar(ctk.CTkProgressBar):
    """CTkProgressBar draws a round nub even at 0%, which reads as progress
    that hasn't happened. Hide the fill until there's something to show."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("progress_color", INK)
        self._fill_color = kwargs["progress_color"]
        super().__init__(*args, **kwargs)

    def set(self, value, **kwargs):
        fill = self._fill_color if value > 0.005 else self.cget("fg_color")
        self.configure(progress_color=fill)
        super().set(value, **kwargs)


def set_enabled(button, enabled):
    """Enable/disable a button, dimming it so a dead control never looks live.
    Only call sites that change state should go through here, not configure()."""
    button.configure(state="normal" if enabled else "disabled")
    # A disabled primary drops its ink fill; otherwise it would still be the
    # brightest thing on screen while doing nothing.
    if getattr(button, "_is_primary", False):
        button.configure(fg_color=INK if enabled else RAISED)
    # Outlined buttons also dim their border when disabled.
    if button.cget("border_width"):
        button.configure(border_color=LINE_STRONG if enabled else LINE)


def make_clickable(widget, command, hover_target=None, base_color=RAISED, hover_color=RAISED_HOVER):
    """Make a whole row (frame + its labels) respond to clicks and hover.
    Child buttons keep their own behavior."""
    target = hover_target or widget

    def on_enter(_):
        if target.winfo_exists():
            target.configure(fg_color=hover_color)

    def on_leave(_):
        if target.winfo_exists():
            target.configure(fg_color=target._clickable_base)

    target._clickable_base = base_color

    def bind_all(w):
        if isinstance(w, (ctk.CTkButton, ctk.CTkSwitch, ctk.CTkOptionMenu)):
            return
        w.bind("<Button-1>", lambda _e: command())
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)
        try:
            w.configure(cursor="hand2")
        except Exception:
            pass
        for child in w.winfo_children():
            bind_all(child)

    bind_all(widget)


def set_row_base(row, color):
    """Change the resting color of a clickable row (e.g. to mark it selected)."""
    row._clickable_base = color
    row.configure(fg_color=color)


def shorten_path(path, max_chars=48):
    """Keep the end of a path, which is the part that identifies it."""
    if not path or len(path) <= max_chars:
        return path or ""
    return "…" + path[-(max_chars - 1):]
