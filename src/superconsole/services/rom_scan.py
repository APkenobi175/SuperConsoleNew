from __future__ import annotations
from pathlib import Path

ROM_EXTS = {
    ".zip", ".7z", ".iso", ".wbfs", ".rvz", ".nsp", ".xci",
    ".nes", ".sfc", ".smc", ".n64", ".z64", ".v64", ".gba", ".gb", ".gbc"
}

def scan_roms(rom_root: Path) -> list[str]:
    if not rom_root.exists():
        return []
    out: list[str] = []
    for p in rom_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in ROM_EXTS:
            out.append(str(p))
    return out
