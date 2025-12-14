from __future__ import annotations
from kivy.app import App
from kivy.uix.label import Label


class SuperConsoleApp(App):
    def __init__(self, rom_count: int, **kwargs):
        super().__init__(**kwargs)
        self.rom_count = rom_count

    def build(self):
        return Label(text=f"SuperConsoleNew\nROMs found: {self.rom_count}")
