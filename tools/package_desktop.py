"""Build a self-contained OpenRPG desktop app for the current operating system."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / "build" / "pyinstaller"


def main() -> None:
    if sys.platform not in ("darwin", "win32"):
        raise SystemExit("Desktop packaging is configured for macOS and Windows.")
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)
    separator = ";" if os.name == "nt" else ":"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--onedir", "--name", "OpenRPG", "--distpath", str(DIST), "--workpath", str(WORK),
        "--specpath", str(WORK), "--add-data", f"{ROOT / 'assets'}{separator}assets",
        "--collect-all", "pygame", "--hidden-import", "pyte", str(ROOT / "main.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    archive = DIST / ("OpenRPG-macOS.zip" if sys.platform == "darwin" else "OpenRPG-Windows.zip")
    source = DIST / "OpenRPG.app" if sys.platform == "darwin" else DIST / "OpenRPG"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in source.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(DIST))
    print(f"Created {archive}")


if __name__ == "__main__":
    main()
