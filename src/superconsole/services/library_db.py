from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    # Good defaults
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA journal_mode = WAL;")      # better concurrent reads
    con.execute("PRAGMA synchronous = NORMAL;")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS games (
            id            INTEGER PRIMARY KEY,
            platform      TEXT    NOT NULL,
            title         TEXT    NOT NULL,

            -- paths stored RELATIVE to ROMS root for portability
            game_dir      TEXT    NOT NULL,
            launch_target TEXT    NOT NULL,
            launch_type   TEXT    NOT NULL CHECK (launch_type IN ('file','dir')),
            cover_path    TEXT,

            -- filesystem fingerprint for incremental updates
            mtime         INTEGER,
            size          INTEGER,

            -- user-facing fields
            favorite      INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0,1)),
            hidden        INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0,1)),
            date_added    TEXT    NOT NULL DEFAULT (datetime('now')),

            last_played   TEXT,
            play_count    INTEGER NOT NULL DEFAULT 0,

            UNIQUE(platform, game_dir)
        );

        CREATE INDEX IF NOT EXISTS idx_games_platform_title
        ON games(platform, title);

        CREATE INDEX IF NOT EXISTS idx_games_favorite
        ON games(favorite);

        CREATE INDEX IF NOT EXISTS idx_games_last_played
        ON games(last_played);
        """
    )
    _ensure_cover_path_column(con)
    con.commit()


from typing import Iterable, Optional, Any, Sequence


def upsert_games(
    con: sqlite3.Connection,
    rows: list[dict[str, Any]],
) -> None:
    """
    Insert or update scanned games.
    We do NOT overwrite user fields like favorite/hidden/date_added/last_played/play_count.
    """
    con.executemany(
        """
        INSERT INTO games (
            platform, title, game_dir, launch_target, launch_type, cover_path, mtime, size
        ) VALUES (
            :platform, :title, :game_dir, :launch_target, :launch_type, :cover_path, :mtime, :size
        )
        ON CONFLICT(platform, game_dir) DO UPDATE SET
            title         = excluded.title,
            launch_target = excluded.launch_target,
            launch_type   = excluded.launch_type,
            cover_path    = excluded.cover_path,
            mtime         = excluded.mtime,
            size          = excluded.size
        """,
        rows,
    )
    con.commit()


def _ensure_cover_path_column(con: sqlite3.Connection) -> None:
    cols = {row[1] for row in con.execute("PRAGMA table_info(games)").fetchall()}
    if "cover_path" in cols:
        return
    con.execute("ALTER TABLE games ADD COLUMN cover_path TEXT;")


def delete_missing_games(con: sqlite3.Connection, platform: str, present_game_dirs: Sequence[str]) -> None:
    """
    Remove rows for games that no longer exist on disk for that platform.
    For large libraries, we’ll upgrade this later to a scan_id approach.
    """
    if not present_game_dirs:
        con.execute("DELETE FROM games WHERE platform = ?", (platform,))
        con.commit()
        return

    # Chunk to avoid SQLite variable limits if needed
    chunk_size = 800
    for i in range(0, len(present_game_dirs), chunk_size):
        chunk = present_game_dirs[i:i+chunk_size]
        placeholders = ",".join(["?"] * len(chunk))
        con.execute(
            f"DELETE FROM games WHERE platform = ? AND game_dir NOT IN ({placeholders})",
            (platform, *chunk),
        )
    con.commit()


def list_games(
    con: sqlite3.Connection,
    platform: Optional[str] = None,
    favorites_only: bool = False,
    search: Optional[str] = None,
) -> list[sqlite3.Row]:
    q = "SELECT * FROM games WHERE hidden = 0"
    params: list[Any] = []

    if platform:
        q += " AND platform = ?"
        params.append(platform)

    if favorites_only:
        q += " AND favorite = 1"

    if search:
        q += " AND title LIKE ?"
        params.append(f"%{search}%")

    q += " ORDER BY title COLLATE NOCASE"
    return list(con.execute(q, params))


def set_favorite(con: sqlite3.Connection, game_id: int, is_fav: bool) -> None:
    con.execute("UPDATE games SET favorite = ? WHERE id = ?", (1 if is_fav else 0, game_id))
    con.commit()


def mark_played(con: sqlite3.Connection, game_id: int) -> None:
    con.execute(
        """
        UPDATE games
        SET last_played = datetime('now'),
            play_count = play_count + 1
        WHERE id = ?
        """,
        (game_id,),
    )
    con.commit()


def update_cover_paths(con: sqlite3.Connection, updates: Sequence[tuple[int, str]]) -> None:
    if not updates:
        return
    con.executemany("UPDATE games SET cover_path = ? WHERE id = ?", updates)
    con.commit()
