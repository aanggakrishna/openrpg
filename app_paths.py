"""Resolve writable per-user storage separately from bundled game assets."""
from pathlib import Path
import os
import sys


def user_data_dir(asset_root: Path) -> Path:
    if not getattr(sys, "frozen", False):
        return asset_root / ".openrpg"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "OpenRPG"
    path.mkdir(parents=True, exist_ok=True)
    return path
