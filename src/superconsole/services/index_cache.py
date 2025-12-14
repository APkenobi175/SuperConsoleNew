from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.models import Game


CACHE_VERSION = 1


def cache_path(project_root: Path) -> Path:
    return project_root / "data" / "cache" / "rom_index.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_games(cache_file: Path, roms_root: Path, games: list[Game]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    # Store paths RELATIVE to roms_root (portable)
    items: list[dict[str, Any]] = []
    for g in games:
        items.append({
            "platform": g.platform,
            "title": g.title,
            "game_dir": str(g.game_dir.relative_to(roms_root)),
            "launch_target": str(g.launch_target.relative_to(roms_root)) if g.launch_target.is_absolute() else str(g.launch_target),
            "launch_is_dir": g.launch_target.is_dir(),
        })

    payload = {
        "version": CACHE_VERSION,
        "generated_at": _now_iso(),
        "roms_root": str(roms_root),
        "count": len(items),
        "items": items,
    }

    cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_games(cache_file: Path, roms_root: Path) -> list[dict[str, Any]] | None:
    """
    Returns raw cached items (dicts). We keep it raw so we can rebuild Game objects
    using current cover lookup (covers may change without rescanning ROMs).
    """
    if not cache_file.exists():
        return None

    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    if payload.get("version") != CACHE_VERSION:
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        return None

    # If cache was generated from a different ROM root, still try to load it
    # (we store relative paths), but you can tighten this later if you want.
    return items
