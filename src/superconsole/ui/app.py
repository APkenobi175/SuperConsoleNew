from __future__ import annotations

import threading
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from ..state import AppState
from ..actions import set_status
from ..services.rom_scanner import scan_roms, ScanConfig
from ..paths import ROMS_DIR, IMAGES_DIR, PROJECT_ROOT

from .screens.home import HomeScreen
from .screens.library import LibraryScreen
from .widgets import LoadingOverlay, COLORS, apply_bg, HoverButton

import time
import subprocess
import shutil
import logging
from ..services.index_cache import cache_path, load_games, save_games
from ..services.covers import find_cover  # uses your exact match version
from ..core.models import Game
from ..services.library_db import (
    connect,
    init_db,
    list_games,
    list_platforms,
    list_favorites,
    list_recently_played,
    list_recently_added,
    update_cover_paths,
    mark_played,
)
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
        self._exit_popup = None
        self._platform_cache = {}

    def _hydrate_rows(self, rows, updates: dict[int, str]) -> list[dict[str, str]]:
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
                updates[r["id"]] = cover_path
            else:
                cover_path = self._resolve_cover_path(cover_path)
            games.append({
                "id": r["id"],
                "title": r["title"],
                "cover_path": cover_path,
                "platform": r["platform"],
                "launch_target": r["launch_target"],
                "launch_type": r["launch_type"],
                "favorite": r["favorite"],
                "last_played": r["last_played"],
                "date_added": r["date_added"],
            })
        return games

    def _load_all_state(self, con):
        updates: dict[int, str] = {}
        rows = list_games(con)
        games = self._hydrate_rows(rows, updates)
        platforms = list_platforms(con)
        favorites = self._hydrate_rows(list_favorites(con), updates)
        recent_played = self._hydrate_rows(list_recently_played(con), updates)
        recent_added = self._hydrate_rows(list_recently_added(con), updates)
        platform_games = {}
        for platform in platforms:
            platform_games[platform] = self._hydrate_rows(list_games(con, platform=platform), updates)

        if updates:
            update_cover_paths(con, [(gid, path) for gid, path in updates.items()])

        return len(rows), games, platforms, favorites, recent_played, recent_added, platform_games

    def _apply_db_state(
        self,
        count: int,
        games: list[dict[str, str]],
        platforms: list[str],
        favorites: list[dict[str, str]],
        recent_played: list[dict[str, str]],
        recent_added: list[dict[str, str]],
        platform_games: dict[str, list[dict[str, str]]],
    ) -> None:
        self.state.rom_count = count
        self.state.roms = games
        self.state.platforms = platforms
        self.state.favorites = favorites
        self.state.recent_played = recent_played
        self.state.recent_added = recent_added
        self._platform_cache = platform_games
        set_status(self.state, f"Loaded DB ({count} ROMs)")
        if count == 0:
            set_status(self.state, "First run: building library...")
            self._rescan_to_db()

    def _load_from_db(self):
        count, games, platforms, favorites, recent_played, recent_added, platform_games = self._load_all_state(self.db)
        self._apply_db_state(count, games, platforms, favorites, recent_played, recent_added, platform_games)

    def _load_from_db_async(self):
        log = logging.getLogger(__name__)

        def worker():
            con = connect(self.db_path)
            init_db(con)
            error = None
            try:
                count, games, platforms, favorites, recent_played, recent_added, platform_games = self._load_all_state(con)
            except Exception as exc:
                error = exc
                count, games, platforms, favorites, recent_played, recent_added, platform_games = 0, [], [], [], [], [], {}
            finally:
                con.close()

            def apply(_dt):
                if error:
                    log.exception("Failed to load DB", exc_info=error)
                    set_status(self.state, "Failed to load DB.")
                else:
                    self._apply_db_state(count, games, platforms, favorites, recent_played, recent_added, platform_games)
                if self._startup_overlay:
                    self._startup_overlay.hide()

            Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()



    def build(self):
        Window.title = "SuperConsole (Ubuntu)" if is_wsl() else "SuperConsole"
        self.sm.add_widget(HomeScreen(self.state, on_rescan=self._rescan_to_db, name="home"))
        self.sm.add_widget(LibraryScreen(self.state, name="platform"))

        log = logging.getLogger(__name__)

        # Route changes switch screens (like a router)
        self.state.bind(route=self._on_route)
        Window.bind(on_key_down=self._on_key_down)
        Window.bind(on_request_close=self._on_request_close)

        # Show startup overlay and load DB in background
        self._startup_overlay = LoadingOverlay(text="Loading library...")
        Clock.schedule_once(lambda *_: self._startup_overlay.show(), 0)
        Clock.schedule_once(lambda *_: self._load_from_db_async(), 0)
        Clock.schedule_once(lambda *_: self._start_hotkey_helper(), 0)
        Clock.schedule_once(lambda *_: self._maximize_window(), 0)

        # Do NOT auto-rescan on every startup

        log.info("Screens registered: %s", list(self.sm.screen_names))
        return self.sm

    def _on_route(self, *_):
        route = self.state.route
        if route.startswith("platform:"):
            platform = route.split(":", 1)[1]
            self.state.current_platform = platform
            self._load_platform_games(platform)
            self.sm.current = "platform"
            return
        if route in self.sm.screen_names:
            self.sm.current = route

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

        log.info("Loaded ROM cache: %d entries", len(games))
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
            if not is_wsl() and hasattr(Window, "minimize"):
                Window.minimize()
            self._emulator_exe = get_emulator_exe(game["platform"])
            if game.get("id"):
                try:
                    mark_played(self.db, game["id"])
                    updates: dict[int, str] = {}
                    recent_played = self._hydrate_rows(list_recently_played(self.db), updates)
                    if updates:
                        update_cover_paths(self.db, [(gid, path) for gid, path in updates.items()])
                    self.state.recent_played = recent_played
                except Exception:
                    log.exception("Failed to mark played: %s", game.get("title", ""))
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

    def _load_platform_games(self, platform: str) -> None:
        if platform in self._platform_cache:
            self.state.current_games = self._platform_cache[platform]
            return

        updates: dict[int, str] = {}
        rows = list_games(self.db, platform=platform)
        games = self._hydrate_rows(rows, updates)
        if updates:
            update_cover_paths(self.db, [(gid, path) for gid, path in updates.items()])
        self._platform_cache[platform] = games
        self.state.current_games = games

    def _on_key_down(self, _window, keycode, _scancode, _codepoint, modifiers):
        key_name = keycode[1] if isinstance(keycode, tuple) else keycode
        if key_name in {"escape", "esc"}:
            self._confirm_exit()
            return True
        if "ctrl" in modifiers and key_name in {"escape", "esc"}:
            self._terminate_emulator()
            return True
        return False

    def _confirm_exit(self) -> None:
        if self._exit_popup and self._exit_popup.parent:
            return
        content = BoxLayout(orientation="vertical", padding=12, spacing=10)
        apply_bg(content, COLORS["panel"])
        content.add_widget(Label(text="Are you sure you want to exit?", color=(1, 1, 1, 1)))
        buttons = BoxLayout(size_hint_y=None, height=44, spacing=10)
        btn_cancel = HoverButton(
            text="Cancel",
            background_color=(0.2, 0.3, 0.4, 1),
            color=(1, 1, 1, 1),
            base_color=(0.2, 0.3, 0.4, 1),
            hover_color=(0.26, 0.38, 0.5, 1),
        )
        btn_exit = HoverButton(
            text="Exit",
            background_color=(0.75, 0.2, 0.2, 1),
            color=(1, 1, 1, 1),
            base_color=(0.75, 0.2, 0.2, 1),
            hover_color=(0.85, 0.28, 0.28, 1),
        )
        buttons.add_widget(btn_cancel)
        buttons.add_widget(btn_exit)
        content.add_widget(buttons)

        popup = Popup(
            title="Exit",
            content=content,
            size_hint=(None, None),
            size=(360, 180),
            auto_dismiss=False,
            background="",
            background_color=(0, 0, 0, 0.65),
        )

        btn_cancel.bind(on_press=lambda *_: popup.dismiss())
        btn_exit.bind(on_press=lambda *_: (popup.dismiss(), self.stop()))
        self._exit_popup = popup
        popup.open()

    def _on_request_close(self, *_args, **_kwargs):
        self._confirm_exit()
        return True

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

    def _maximize_window(self) -> None:
        try:
            Window.fullscreen = "auto"
        except Exception:
            pass

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
