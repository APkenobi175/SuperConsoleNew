from __future__ import annotations
from pathlib import Path




PROJECT_ROOT=Path(__file__).resolve().parents[2] # Go up two levels to reach the project root

DATA_DIR=PROJECT_ROOT / "data" # Data directory

ROMS_DIR=DATA_DIR / "roms" # ROMS
IMAGES_DIR=DATA_DIR / "images" # Images
BIOS_DIR=DATA_DIR / "bios" # BIOS files
EMULATORS_DIR=DATA_DIR / "emulators" # Emulators
VIDEOS_DIR=DATA_DIR / "videos" # Videos

def is_symlink(path:Path) -> bool:
    """Check if a given path is a symlink."""
    try:
        return path.is_symlink()
    except OSError:
        return False


