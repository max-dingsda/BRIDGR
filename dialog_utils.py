from __future__ import annotations

from pathlib import Path
from tkinter import Tk, filedialog


def pick_directory(initial_path: str) -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected_path = filedialog.askdirectory(initialdir=_safe_initial_dir(initial_path))
    finally:
        root.destroy()
    return selected_path or None


def pick_file(initial_path: str, filetypes: list[tuple[str, str]]) -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected_path = filedialog.askopenfilename(
            initialdir=_safe_initial_dir(initial_path),
            filetypes=filetypes,
        )
    finally:
        root.destroy()
    return selected_path or None


def _safe_initial_dir(initial_path: str) -> str:
    path = Path(initial_path)
    if path.is_file():
        path = path.parent
    if path.exists():
        return str(path)
    return str(Path.cwd())
