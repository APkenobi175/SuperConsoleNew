from __future__ import annotations

import threading
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from ..state import AppState
from ..actions import set_status
from ..services.rom_scanner import scan_roms, ScanConfig
from ..paths import ROMS_DIR, IMAGES_DIR, PROJECT_ROOT

from .screens.home import HomeScreen
from .screens.library import LibraryScreen
from .widgets import LoadingOverlay

import time
import subprocess
import shutil
import logging
from ..services.index_cache import cache_path, load_games, save_games
from ..services.covers import find_cover  # uses your exact match version
from ..core.models import Game
from ..services.library_db import connect, init_db, list_games, update_cover_paths
from ..services.library_sync import sync_library
from ..services.game_launcher import launch_game, is_wsl, get_emulator_exe



PLACEHOLDER = PROJECT_ROOT / "src" / "superconsole" / "ui" / "assets" / "default_cover.png"


class SuperConsoleApp(App):
    def __init__(self, state: AppState, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.sm = ScreenManager(transition=FadeTransition())
        self.db_path = PROJECT_ROOT / "data" / "db" / "superconsole.sqlite3"
        self.db = connect(self.db_path)
        init_db(self.db)
        self._scan_log_event = None
        self._startup_overlay = None
        self._emulator_proc = None
        self._emulator_exe = None
        self._hotkey_proc = None

    def _prepare_db_state(self, con):
        rows = list_games(con)
        updates: list[tuple[int, str]] = []
        games = []
        for r in rows:
            cover_path = r["cover_path"]
            if not cover_path:
                cover = find_cover(
                    r["platform"],
                    Path(r["game_dir"]).name,
                    IMAGES_DIR,
                    PLACEHOLDER,
                )
                cover_path = self._resolve_cover_path(str(cover))
                updates.append((r["id"], cover_path))
            else:
                cover_path = self._resolve_cover_path(cover_path)
            games.append({
                "title": r["title"],
                "cover_path": cover_path,
                "platform": r["platform"],
                "launch_target": r["launch_target"],
                "launch_type": r["launch_type"],
            })
        update_cover_paths(con, updates)
        return len(rows), games

    def _apply_db_state(self, count: int, games: list[dict[str, str]]) -> None:
        self.state.rom_count = count
        self.state.roms = games
        set_status(self.state, f"Loaded DB ({count} ROMs)")
        if count == 0:
            set_status(self.state, "First run: building library...")
            self._rescan_to_db()

    def _load_from_db(self):
        count, games = self._prepare_db_state(self.db)
        self._apply_db_state(count, games)

    def _load_from_db_async(self):
        log = logging.getLogger(__name__)

        def worker():
            con = connect(self.db_path)
            init_db(con)
            error = None
            try:
                count, games = self._prepare_db_state(con)
            except Exception as exc:
                error = exc
                count, games = 0, []
            finally:
                con.close()

            def apply(_dt):
                if error:
                    log.exception("Failed to load DB", exc_info=error)
                    set_status(self.state, "Failed to load DB.")
                else:
                    self._apply_db_state(count, games)
                if self._startup_overlay:
                    self._startup_overlay.hide()

            Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()



    def build(self):
        Window.title = "SuperConsole (Ubuntu)" if is_wsl() else "SuperConsole"
        self.sm.add_widget(HomeScreen(self.state, on_rescan=self._rescan_to_db, name="home"))
        self.sm.add_widget(LibraryScreen(self.state, name="library"))

        log = logging.getLogger(__name__)

        # Route changes switch screens (like a router)
        self.state.bind(route=self._on_route)
        Window.bind(on_key_down=self._on_key_down)

        # Show startup overlay and load DB in background
        self._startup_overlay = LoadingOverlay(text="Loading library...")
        Clock.schedule_once(lambda *_: self._startup_overlay.show(), 0)
        Clock.schedule_once(lambda *_: self._load_from_db_async(), 0)
        Clock.schedule_once(lambda *_: self._start_hotkey_helper(), 0)

        # Do NOT auto-rescan on every startup

        log.info("Screens registered: %s", list(self.sm.screen_names))
        return self.sm

    def _on_route(self, *_):
        if self.state.route in self.sm.screen_names:
            self.sm.current = self.state.route

    def _load_cache_into_state(self) -> bool:
        import logging
        from ..services.index_cache import cache_path, load_games

        log = logging.getLogger(__name__)
        cpath = cache_path(PROJECT_ROOT)
        cached = load_games(cpath, ROMS_DIR)
        if not cached:
            return False

        # FAST: just titles/platforms/count (no cover checks on /mnt/e)
        games = []
        for item in cached:
            cover_path = item.get("cover_path")
            if not cover_path:
                cover = find_cover(
                    item.get("platform", ""),
                    Path(item.get("game_dir", "")).name,
                    IMAGES_DIR,
                    PLACEHOLDER,
                )
                cover_path = str(cover)
            games.append({
                "title": item.get("title", ""),
                "cover_path": self._resolve_cover_path(cover_path),
                "platform": item.get("platform", ""),
                "launch_target": item.get("launch_target", ""),
                "launch_type": "dir" if item.get("launch_is_dir") else "file",
            })

        self.state.roms = games
        self.state.rom_count = len(games)
        set_status(self.state, f"Loaded cache ({len(games)} ROMs)")

        log.info("Loaded ROM cache: %d entries", len(titles))
        return True


    def _start_rom_scan(self, force: bool = False):
        from ..services.index_cache import cache_path
        if not force and cache_path(PROJECT_ROOT).exists():
            return # skip scan if cache exists, and only scan if user requests it

        import time
        import logging

        log = logging.getLogger(__name__)


        if self.state.scan_in_progress:
            return

        self.state.scan_in_progress = True
        set_status(self.state, "Scanning ROMs...")

        t0 = time.time()
        self._start_scan_log_timer(log, t0)

        def worker():
            cfg = ScanConfig(
                roms_root=ROMS_DIR,
                images_root=IMAGES_DIR,
                placeholder_cover=PLACEHOLDER,
            )
            games = scan_roms(cfg)

            # Save cache
            from ..services.index_cache import cache_path, save_games
            try:
                save_games(cache_path(PROJECT_ROOT), ROMS_DIR, IMAGES_DIR, games)
            except Exception as e:
                log.warning("Failed to save cache: %s", e)

            def apply(_dt):
                self.state.roms = [
                    {
                        "title": g.title,
                        "cover_path": str(g.cover_path),
                        "platform": g.platform,
                        "launch_target": str(g.launch_target),
                        "launch_type": "dir" if g.launch_target.is_dir() else "file",
                    }
                    for g in games
                ]
                self.state.rom_count = len(games)
                self.state.scan_in_progress = False
                self._stop_scan_log_timer()
                elapsed = time.time() - t0
                log.info("Rescanning roms....%.1fs", elapsed)
                log.info("Scan Complete")
                set_status(self.state, f"Ready ({len(games)} ROMs, scanned in {time.time() - t0:.1f}s)")

            Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()

    def _resolve_cover_path(self, cover_path: str | None) -> str:
        if not cover_path:
            return str(PLACEHOLDER)
        p = Path(cover_path)
        if not p.is_absolute():
            return str(IMAGES_DIR / p)
        return str(p)

    def launch_game(self, game: dict[str, str]) -> None:
        import logging
        log = logging.getLogger(__name__)
        try:
            if hasattr(Window, "minimize"):
                Window.minimize()
            self._emulator_exe = get_emulator_exe(game["platform"])
            proc = launch_game(game["platform"], game["launch_target"])
            self._emulator_proc = proc
            if not is_wsl() and proc is not None:
                def _restore(_dt):
                    try:
                        if hasattr(Window, "restore"):
                            Window.restore()
                        if hasattr(Window, "raise_window"):
                            Window.raise_window()
                    except Exception:
                        pass

                def _wait():
                    try:
                        proc.wait()
                    finally:
                        Clock.schedule_once(_restore, 0)

                threading.Thread(target=_wait, daemon=True).start()
        except Exception:
            log.exception("Failed to launch game: %s", game.get("title", ""))

    def _on_key_down(self, _window, keycode, _scancode, _codepoint, modifiers):
        key_name = keycode[1] if isinstance(keycode, tuple) else keycode
        if "ctrl" in modifiers and key_name in {"escape", "esc"}:
            self._terminate_emulator()
            return True
        return False

    def _terminate_emulator(self) -> None:
        import logging
        import subprocess

        log = logging.getLogger(__name__)
        if not self._emulator_exe:
            return

        exe_name = self._emulator_exe.name

        if is_wsl():
            try:
                subprocess.Popen(["cmd.exe", "/c", "taskkill", "/IM", exe_name, "/F"])
            except Exception:
                log.exception("Failed to taskkill emulator on WSL")
        else:
            if self._emulator_proc and self._emulator_proc.poll() is None:
                try:
                    self._emulator_proc.terminate()
                except Exception:
                    log.exception("Failed to terminate emulator process")
            try:
                subprocess.Popen(["taskkill", "/IM", exe_name, "/F"])
            except Exception:
                pass

        self._emulator_proc = None

        try:
            if hasattr(Window, "restore"):
                Window.restore()
            if hasattr(Window, "raise_window"):
                Window.raise_window()
        except Exception:
            pass

    def _start_hotkey_helper(self) -> None:
        import logging
        log = logging.getLogger(__name__)
        script = PROJECT_ROOT / "scripts" / "superconsole_hotkeys.ahk"
        if not script.exists():
            log.warning("AutoHotkey script not found: %s", script)
            return

        if is_wsl():
            script_win = self._wsl_to_windows_path(script)
            if not script_win:
                log.warning("Hotkey helper not started (wslpath failed).")
                return
            try:
                log.info("Running AutoHotkey script...")
                check = subprocess.run(
                    ["cmd.exe", "/c", "where", "AutoHotkey.exe"],
                    capture_output=True,
                    text=True,
                )
                ahk_exe = "AutoHotkey.exe"
                if check.returncode != 0:
                    ahk_exe = r"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe"
                self._hotkey_proc = subprocess.Popen(
                    ["cmd.exe", "/c", "start", "", ahk_exe, script_win]
                )
                log.info("AutoHotkey script started.")
            except Exception:
                log.exception("Failed to start AutoHotkey helper from WSL.")
            return

        exe = (
            shutil.which("AutoHotkey.exe")
            or shutil.which("AutoHotkey")
            or r"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe"
        )
        if not exe:
            log.warning("AutoHotkey.exe not found on PATH.")
            return
        try:
            log.info("Running AutoHotkey script...")
            self._hotkey_proc = subprocess.Popen([exe, str(script)])
            log.info("AutoHotkey script started.")
        except Exception:
            log.exception("Failed to start AutoHotkey helper.")

    def _wsl_to_windows_path(self, path: Path) -> str | None:
        try:
            result = subprocess.run(
                ["wslpath", "-w", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except Exception:
            return None

    def _rescan_to_db(self, force: bool = False):
        if self.state.scan_in_progress:
            return

        self.state.scan_in_progress = True
        set_status(self.state, "Scanning ROMs...")

        log = logging.getLogger(__name__)
        t0 = time.time()
        self._start_scan_log_timer(log, t0)

        def worker():
            cfg = ScanConfig(
                roms_root=ROMS_DIR,
                images_root=IMAGES_DIR,
                placeholder_cover=PLACEHOLDER,
            )
            con = connect(self.db_path)
            init_db(con)
            try:
                count = sync_library(con, cfg)
            finally:
                con.close()

            def apply(_dt):
                self.state.scan_in_progress = False
                self._load_from_db()
                self._stop_scan_log_timer()
                elapsed = time.time() - t0
                log.info("Rescanning roms....%.1fs", elapsed)
                log.info("Scan Complete")
                set_status(self.state, f"Ready ({count} ROMs)")

            Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()

    def _start_scan_log_timer(self, log, start_time: float) -> None:
        def _tick(_dt):
            elapsed = time.time() - start_time
            log.info("Rescanning roms....%.1fs", elapsed)
        self._stop_scan_log_timer()
        log.info("Rescanning roms....0.0s")
        self._scan_log_event = Clock.schedule_interval(_tick, 5.0)

    def _stop_scan_log_timer(self) -> None:
        if self._scan_log_event is not None:
            self._scan_log_event.cancel()
            self._scan_log_event = None
