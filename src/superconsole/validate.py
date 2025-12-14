from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import logging

from .paths import DATA_DIR, ROMS_DIR, IMAGES_DIR, BIOS_DIR, EMULATORS_DIR, VIDEOS_DIR, is_symlink

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class ValidationResult:
    rom_count: int

def _count_files(root: Path, exts: set[str] | None = None) -> int:
    if not root.exists():
        return 0 
    
    count = 0
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        if exts is None:
            count += 1
            continue
        if p.suffix.lower() in exts:
            count += 1
    return count


def validate_or_raise() -> ValidationResult:
    if not DATA_DIR.exists():
        raise RuntimeError(f"Data directory does not exist: {DATA_DIR}")

    required = {
        "roms": ROMS_DIR,
        "images": IMAGES_DIR,
        "bios": BIOS_DIR,
        "emulators": EMULATORS_DIR,
        "videos": VIDEOS_DIR,   
    }

    problems: list[str] = []

    for name, path in required.items():
        if not path.exists():
            problems.append(f"Required directory '{name}' does not exist at path: {path}")
            continue
        if not is_symlink(path):
            log.warning(f"Directory '{name}' at path {path} is not a symlink, That is OK if intentional")
    if problems:
        msg = "Validation failed with the following problems:\n" + "\n".join(problems)
        raise RuntimeError(msg)

    rom_count = _count_files(ROMS_DIR, exts = {".zip", ".7z", ".iso", ".wbfs", ".rvz", ".nsp", ".xci", ".nes", ".sfc", ".smc", ".n64", ".z64", ".v64", ".gba", ".gb", ".gbc"})
    log.info(f"Found {rom_count} ROM files in {ROMS_DIR}")

    return ValidationResult(rom_count=rom_count)


