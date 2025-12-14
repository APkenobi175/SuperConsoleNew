from __future__ import annotations

import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from ..state import AppState
from ..actions import set_status
from ..services.rom_scanner import scan_roms, ScanConfig
from ..paths import ROMS_DIR, IMAGES_DIR, PROJECT_ROOT

from .screens.home import HomeScreen
from .screens.library import LibraryScreen

import time
import logging
from ..services.index_cache import cache_path, load_games, save_games
from ..services.covers import find_cover  # uses your exact match version
from ..core.models import Game


PLACEHOLDER = PROJECT_ROOT / "src" / "superconsole" / "ui" / "assets" / "default_cover.png"


class SuperConsoleApp(App):
    def __init__(self, state: AppState, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.sm = ScreenManager(transition=FadeTransition())

    def build(self):
        self.sm.add_widget(HomeScreen(self.state, name="home"))
        self.sm.add_widget(LibraryScreen(self.state, name="library"))
        log = logging.getLogger(__name__)

        # Route changes switch screens (like a router)
        self.state.bind(route=self._on_route)

        # Kick off background scan after UI starts
        Clock.schedule_once(lambda *_: self._load_cache_into_state(), 0)
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
        titles = [item["title"] for item in cached]

        self.state.roms = titles
        self.state.rom_count = len(titles)
        set_status(self.state, f"Loaded cache ({len(titles)} ROMs)")

        log.info("Loaded ROM cache: %d entries", len(titles))
        return True


    def _start_rom_scan(self):
        from ..services.index_cache import cache_path
        if cache_path(PROJECT_ROOT).exists():
            return # skip scan if cache exists, and only scan if user requests it

        import time
        import logging

        log = logging.getLogger(__name__)


        if self.state.scan_in_progress:
            return

        self.state.scan_in_progress = True
        set_status(self.state, "Scanning ROMs...")

        def worker():
            t0 = time.time()
            cfg = ScanConfig(
                roms_root=ROMS_DIR,
                images_root=IMAGES_DIR,
                placeholder_cover=PLACEHOLDER,
            )
            games = scan_roms(cfg)

            # Save cache
            from ..services.index_cache import cache_path, save_games
            try:
                save_games(cache_path(PROJECT_ROOT), ROMS_DIR, games)
            except Exception as e:
                log.warning("Failed to save cache: %s", e)

            def apply(_dt):
                self.state.roms = [g.title for g in games]  # temporary
                self.state.rom_count = len(games)
                self.state.scan_in_progress = False
                set_status(self.state, f"Ready ({len(games)} ROMs, scanned in {time.time() - t0:.1f}s)")

            Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()
