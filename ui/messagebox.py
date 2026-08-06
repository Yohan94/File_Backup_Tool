import tkinter
from CTkMessagebox import CTkMessagebox as _CTkMessagebox


def CTkMessagebox(*args, **kwargs):
    """Drop-in replacement for CTkMessagebox that forces the dialog to the
    foreground and onto the same monitor as the main window.

    The library sets -topmost but never grabs OS focus, so on Windows the
    popup can render behind the currently focused main window. It also
    centers itself on the primary monitor whenever no `master` is given,
    which strands it on the wrong screen in multi-monitor setups.
    """
    if "master" not in kwargs and len(args) == 0:
        kwargs["master"] = tkinter._default_root
    box = _CTkMessagebox(*args, **kwargs)
    box.after(10, lambda: box.winfo_exists() and (box.lift(), box.focus_force()))
    return box
