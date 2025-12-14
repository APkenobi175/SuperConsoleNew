from __future__ import annotations
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from ..state import AppState
from ..paths import ROMS_DIR
from ..actions import set_status
from ..services.rom_scan import scan_roms

from .screens.home import HomeScreen
from .screens.library import LibraryScreen

class SuperConsoleApp(App):
    def __init__(self, state: AppState, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.sm = ScreenManager(transition=FadeTransition())

    def build(self):
        self.sm.add_widget(HomeScreen(self.state, name="home"))
        self.sm.add_widget(LibraryScreen(self.state, name="library"))

        # Route changes switch screens (like a router)
        self.state.bind(route=self._on_route)

        # Kick off background scan after UI starts
        Clock.schedule_once(lambda *_: self._start_rom_scan(), 0)

        return self.sm

    def _on_route(self, *_):
        if self.state.route in self.sm.screen_names:
            self.sm.current = self.state.route

    def _start_rom_scan(self):
        if self.state.scan_in_progress:
            return
        self.state.scan_in_progress = True
        set_status(self.state, "Scanning ROMs...")

        def worker():
            roms = scan_roms(ROMS_DIR)

            def apply(_dt):
                self.state.roms = roms
                self.state.rom_count = len(roms)
                self.state.scan_in_progress = False
                set_status(self.state, "Ready")

            Clock.schedule_once(apply, 0)

        threading.Thread(target=worker, daemon=True).start()
