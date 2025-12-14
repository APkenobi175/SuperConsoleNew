from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..core.models import Game
from .covers import find_cover

# Files we never treat as "the game"
IGNORE_EXTS = {
    ".srm", ".sav", ".state", ".png", ".jpg", ".jpeg", ".webp",
    ".txt", ".nfo", ".pdf", ".ini", ".cfg", ".db",
    ".wbf1", ".wbf2", ".wbf3",  # Wii split chunks (the .wbfs is the entry)
}

# Basic playable extensions by platform type (folder-per-game)
EXTS_DEFAULT = {".nes", ".sfc", ".smc", ".gba", ".gb", ".gbc", ".z64", ".n64", ".v64", ".iso", ".rvz"}
EXTS_PS2 = {".iso", ".chd"}
EXTS_XBOX = {".iso", ".xiso"}
EXTS_WII = {".wbfs", ".rvz", ".iso"}       # only treat .wbfs as entry, ignore .wbf1 chunks
EXTS_GAMECUBE = {".iso", ".rvz"}
EXTS_PS1 = {".cue"}                        # cue is the entry point
EXTS_WIIU = set()                          # folder-based
EXTS_PS3 = {".iso"}                        # optional; installed games handled separately

@dataclass(frozen=True)
class ScanConfig:
    roms_root: Path
    images_root: Path
    placeholder_cover: Path

    # Optional: scan installed PS3 games from RPCS3 dev_hdd0
    rpcs3_dev_hdd0_game: Path | None = None  # e.g. /mnt/e/.../RPCS3/dev_hdd0/game
    ps3_platform_name: str = "ps3"


def _iter_game_dirs(platform_dir: Path) -> Iterable[Path]:
    for p in sorted(platform_dir.iterdir()):
        if p.is_dir():
            yield p


def _pick_first_file_with_exts(game_dir: Path, exts: set[str]) -> Path | None:
    # Prefer deterministic ordering
    candidates: list[Path] = []
    for p in sorted(game_dir.iterdir()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in IGNORE_EXTS:
            continue
        if ext in exts:
            candidates.append(p)
    return candidates[0] if candidates else None


def _pick_launch_target(platform: str, game_dir: Path) -> Path | None:
    p = platform.lower()

    # PS1: use .cue
    if p in {"ps1", "playstation", "playstation1"}:
        return _pick_first_file_with_exts(game_dir, EXTS_PS1)

    # WiiU: folder game, detect via meta/meta.xml OR code/*.rpx
    if p in {"wiiu", "wii-u"}:
        meta_xml = game_dir / "meta" / "meta.xml"
        if meta_xml.exists():
            return game_dir  # launch folder
        code_dir = game_dir / "code"
        if code_dir.is_dir():
            # choose first .rpx for tools that want direct executable
            for f in sorted(code_dir.iterdir()):
                if f.is_file() and f.suffix.lower() == ".rpx":
                    return f
        return None

    # Wii: prefer .wbfs in folder; ignore .wbf1
    if p == "wii":
        return _pick_first_file_with_exts(game_dir, EXTS_WII)

    # GameCube
    if p == "gamecube":
        return _pick_first_file_with_exts(game_dir, EXTS_GAMECUBE)

    # PS2
    if p == "ps2":
        return _pick_first_file_with_exts(game_dir, EXTS_PS2)

    # Xbox / 360
    if p == "xbox":
        return _pick_first_file_with_exts(game_dir, EXTS_XBOX)
    if p in {"xbox360", "xbox-360"}:
        return _pick_first_file_with_exts(game_dir, EXTS_XBOX)

    # PS3 folder games (RPCS3 style): look for PS3_GAME/USRDIR/EBOOT.BIN
    if p == "ps3":
        eboot = game_dir / "PS3_GAME" / "USRDIR" / "EBOOT.BIN"
        if eboot.exists():
            return eboot
        # optional iso
        return _pick_first_file_with_exts(game_dir, EXTS_PS3)

    # Default: find first supported ROM-like file
    return _pick_first_file_with_exts(game_dir, EXTS_DEFAULT)


def scan_roms(config: ScanConfig) -> list[Game]:
    games: list[Game] = []

    if not config.roms_root.exists():
        return games

    # Platforms are directories under ROMS/
    for platform_dir in sorted(config.roms_root.iterdir()):
        if not platform_dir.is_dir():
            continue

        platform = platform_dir.name

        # Ignore PS3 asset buckets inside ROMS/ps3
        if platform.lower() == "ps3":
            # We'll still scan for PS3 folder-games, but skip exdata/packages if present
            pass

        for game_dir in _iter_game_dirs(platform_dir):
            name_lower = game_dir.name.lower()
            if platform.lower() == "ps3" and name_lower in {"exdata", "packages"}:
                continue

            launch_target = _pick_launch_target(platform, game_dir)
            if not launch_target:
                continue

            cover = find_cover(platform, game_dir.name, config.images_root, config.placeholder_cover)

            games.append(Game(
                platform=platform,
                title=game_dir.name,
                game_dir=game_dir,
                launch_target=launch_target,
                cover_path=cover,
            ))

    # Optional: installed PS3 games in RPCS3 dev_hdd0/game/<TITLEID>/USRDIR/EBOOT.BIN
    if config.rpcs3_dev_hdd0_game and config.rpcs3_dev_hdd0_game.exists():
        ps3_platform = config.ps3_platform_name
        for title_id_dir in sorted(config.rpcs3_dev_hdd0_game.iterdir()):
            if not title_id_dir.is_dir():
                continue
            eboot = title_id_dir / "USRDIR" / "EBOOT.BIN"
            if not eboot.exists():
                continue

            cover = find_cover(ps3_platform, title_id_dir.name, config.images_root, config.placeholder_cover)

            games.append(Game(
                platform=ps3_platform,
                title=title_id_dir.name,
                game_dir=title_id_dir,
                launch_target=eboot,
                cover_path=cover,
            ))

    return games
