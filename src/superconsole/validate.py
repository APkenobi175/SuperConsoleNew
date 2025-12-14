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
        raise RuntimeError(f"Missing data directory: {DATA_DIR}")

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
            problems.append(f"- Missing: data/{name} (expected at {path})")
            continue

        if not is_symlink(path):
            log.warning("data/%s is not a symlink (OK if intentional): %s", name, path)

    if problems:
        msg = "Project data validation failed:\n" + "\n".join(problems)
        raise RuntimeError(msg)

    # IMPORTANT: do NOT scan ROMs here. That happens asynchronously after the UI starts.
    log.info("Validation OK (skipping ROM count at startup).")
    return ValidationResult(rom_count=0)



