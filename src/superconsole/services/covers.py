from __future__ import annotations
from pathlib import Path
from ..core.titles import clean_title

COVER_EXTS = (".png", ".jpg", ".jpeg", ".webp")

def find_cover(platform: str, game_folder_name: str, images_root: Path, placeholder: Path) -> Path:
    """
    Looks in: IMAGES/<platform>/covers/<game_folder_name>.(png/jpg/...)
    Falls back to fuzzy match on cleaned title if exact not found.
    """
    covers_dir = images_root / platform / "covers"
    if not covers_dir.exists():
        return placeholder

    # 1) exact match
    for ext in COVER_EXTS:
        p = covers_dir / f"{game_folder_name}{ext}"
        if p.exists():
            return p

    # 2) fuzzy match (optional, but helps)
    target_clean = clean_title(game_folder_name)
    for p in covers_dir.iterdir():
        if p.is_file() and p.suffix.lower() in COVER_EXTS:
            if clean_title(p.stem) == target_clean:
                return p

    return placeholder
