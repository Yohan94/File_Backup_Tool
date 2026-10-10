import os
import tempfile
import tkinter
from CTkMessagebox import CTkMessagebox as _CTkMessagebox

from ui import theme

_ICON_NAMES = ("check", "cancel", "info", "question", "warning")
_gray_icon_cache = {}


def _grayscale_icon(name):
    """The library ships colored PNG icons; convert them once to grayscale so
    dialogs match the rest of the app. Falls back to the stock icon."""
    if name not in _ICON_NAMES:
        return name
    if name in _gray_icon_cache:
        return _gray_icon_cache[name]
    try:
        from PIL import Image
        import CTkMessagebox as pkg
        src = os.path.join(os.path.dirname(pkg.__file__), "icons", f"{name}.png")
        out_dir = os.path.join(tempfile.gettempdir(), "smart_backup_icons")
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, f"{name}.png")
        if not os.path.exists(dst):
            img = Image.open(src).convert("RGBA")
            alpha = img.getchannel("A")
            gray = img.convert("L").point(lambda v: 150 + v * 90 // 255)
            Image.merge("LA", (gray, alpha)).save(dst)
        _gray_icon_cache[name] = dst
    except Exception:
        _gray_icon_cache[name] = name
    return _gray_icon_cache[name]


def CTkMessagebox(*args, **kwargs):
    """Drop-in replacement for CTkMessagebox that forces the dialog to the
    foreground and onto the same monitor as the main window, styled in the
    app's grayscale theme.

    The library sets -topmost but never grabs OS focus, so on Windows the
    popup can render behind the currently focused main window. It also
    centers itself on the primary monitor whenever no `master` is given,
    which strands it on the wrong screen in multi-monitor setups.
    """
    if "master" not in kwargs and len(args) == 0:
        kwargs["master"] = tkinter._default_root
    kwargs["icon"] = _grayscale_icon(kwargs.get("icon", "info"))
    kwargs.setdefault("font", theme.FONT_BODY)
    kwargs.setdefault("corner_radius", theme.RADIUS)
    kwargs.setdefault("width", 420)
    kwargs.setdefault("fade_in_duration", 0)
    box = _CTkMessagebox(*args, **kwargs)
    box.after(10, lambda: box.winfo_exists() and (box.lift(), box.focus_force()))
    return box
