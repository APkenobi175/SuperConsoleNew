from __future__ import annotations
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from ...actions import set_route

class HomeScreen(Screen):
    def __init__(self, state, **kwargs):
        super().__init__(**kwargs)
        self.state = state

        root = BoxLayout(orientation="vertical", padding=20, spacing=12)

        self.title = Label(text="SuperConsoleNew", font_size="28sp", size_hint_y=None, height=50)
        self.roms = Label(text="ROMs found: 0", font_size="18sp", size_hint_y=None, height=40)
        self.status = Label(text="Ready", font_size="16sp", size_hint_y=None, height=30)

        btn = Button(text="Go to Library", size_hint_y=None, height=48)
        btn.bind(on_press=lambda *_: set_route(self.state, "library"))

        root.add_widget(self.title)
        root.add_widget(self.roms)
        root.add_widget(self.status)
        root.add_widget(btn)
        self.add_widget(root)

        # Reactive bindings (web-app vibe)
        self.state.bind(rom_count=self._on_rom_count)
        self.state.bind(status_text=self._on_status)

        scan_btn = Button(text="Rescan ROMs", size_hint_y=None, height=48)
        scan_btn.bind(on_press=lambda *_: self.manager.app._start_rom_scan())
        root.add_widget(scan_btn)

    def _on_rom_count(self, *_):
        self.roms.text = f"ROMs found: {self.state.rom_count}"

    def _on_status(self, *_):
        self.status.text = self.state.status_text
