from __future__ import annotations
from pathlib import Path
import re
from ..core.titles import clean_title

COVER_EXTS = (".png", ".jpg", ".jpeg", ".webp")

def find_cover(platform: str, game_folder_name: str, images_root: Path, placeholder: Path) -> Path:
    """
    Looks in: IMAGES/<platform>/covers/<game_folder_name>.(png/jpg/...)
    Falls back to fuzzy match on cleaned title if exact not found.
    """
    covers_dir = images_root / platform / "covers"
    platform_dir = images_root / platform
    if not covers_dir.exists() and not platform_dir.exists():
        return placeholder

    search_dirs = [covers_dir, platform_dir]

    # 1) exact match
    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        for ext in COVER_EXTS:
            p = base_dir / f"{game_folder_name}{ext}"
            if p.exists():
                return p

    # 1b) platform codes for GameCube/Wii (IDs stored in covers dir)
    if platform.lower() in {"gamecube", "wii"}:
        code = _extract_disc_id(game_folder_name)
        if code:
            for base_dir in search_dirs:
                if not base_dir.exists():
                    continue
                for ext in COVER_EXTS:
                    p = base_dir / f"{code}{ext}"
                    if p.exists():
                        return p

    # 2) fuzzy match (optional, but helps)
    target_clean = clean_title(game_folder_name)
    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        for p in base_dir.iterdir():
            if p.is_file() and p.suffix.lower() in COVER_EXTS:
                if clean_title(p.stem) == target_clean:
                    return p

    return placeholder


def _extract_disc_id(name: str) -> str | None:
    candidates = re.findall(r"[A-Za-z0-9]{6}", name)
    if not candidates:
        return None
    return candidates[-1].upper()
