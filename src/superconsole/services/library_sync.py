from __future__ import annotations

from pathlib import Path
from typing import Any

from .rom_scanner import scan_roms, ScanConfig
from .library_db import upsert_games, delete_missing_games
from ..core.models import Game


def _file_fingerprint(path: Path) -> tuple[int | None, int | None]:
    try:
        st = path.stat()
        return int(st.st_mtime), int(st.st_size)
    except OSError:
        return None, None


def sync_library(con, cfg: ScanConfig) -> int:
    games: list[Game] = scan_roms(cfg)

    rows: list[dict[str, Any]] = []
    present_by_platform: dict[str, list[str]] = {}

    for g in games:
        # store paths relative to ROMS root
        game_dir_rel = str(g.game_dir.relative_to(cfg.roms_root))
        launch_rel = str(g.launch_target.relative_to(cfg.roms_root)) if g.launch_target.is_absolute() else str(g.launch_target)
        cover_rel = _cover_path_rel(g.cover_path, cfg.images_root)

        # fingerprint: if launch_target is a folder (WiiU), fingerprint the folder itself (mtime changes on updates)
        mtime, size = _file_fingerprint(g.launch_target)

        rows.append({
            "platform": g.platform,
            "title": g.title,
            "game_dir": game_dir_rel,
            "launch_target": launch_rel,
            "launch_type": "dir" if g.launch_target.is_dir() else "file",
            "cover_path": cover_rel,
            "mtime": mtime,
            "size": size,
        })
        present_by_platform.setdefault(g.platform, []).append(game_dir_rel)

    upsert_games(con, rows)

    # delete missing per platform
    for platform, present in present_by_platform.items():
        delete_missing_games(con, platform, present)

    return len(games)


def _cover_path_rel(cover_path: Path, images_root: Path) -> str:
    if cover_path.is_absolute():
        try:
            return str(cover_path.relative_to(images_root))
        except ValueError:
            return str(cover_path)
    return str(cover_path)
