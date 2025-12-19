from __future__ import annotations
import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

from ...actions import set_route
from ..widgets import (
    COLORS,
    apply_bg,
    TabButton,
    SectionHeader,
    SearchInput,
    LoadingOverlay,
    build_game_grid,
)

class HomeScreen(Screen):
    def __init__(self, state, on_rescan=None, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.on_rescan = on_rescan
        self._search_text = ""
        self.log = logging.getLogger(__name__)

        root = BoxLayout(orientation="vertical", padding=16, spacing=10)
        apply_bg(root, COLORS["bg"])

        header = BoxLayout(size_hint_y=None, height=44, padding=[10, 6], spacing=8)
        apply_bg(header, COLORS["panel"])
        self.title = Label(
            text="SuperConsole",
            font_size="20sp",
            color=COLORS["text"],
            bold=True,
            halign="left",
            valign="middle",
        )
        self.title.bind(size=self.title.setter("text_size"))
        self.status = Label(
            text="Ready",
            font_size="12sp",
            color=COLORS["muted"],
            halign="right",
            valign="middle",
        )
        self.status.bind(size=self.status.setter("text_size"))
        header.add_widget(self.title)
        header.add_widget(self.status)

        tab_bar = BoxLayout(size_hint_y=None, height=46, padding=[6, 6], spacing=8)
        apply_bg(tab_bar, COLORS["panel_alt"])
        home_btn = TabButton("Home")
        home_btn.set_active(True)
        lib_btn = TabButton("Library")
        lib_btn.bind(on_release=lambda *_: self._log_and_route("Library", "library"))
        tab_bar.add_widget(home_btn)
        tab_bar.add_widget(lib_btn)

        search_bar = BoxLayout(size_hint_y=None, height=42, padding=[8, 6], spacing=8)
        apply_bg(search_bar, COLORS["panel"])
        search_label = Label(
            text="Search",
            font_size="14sp",
            color=COLORS["muted"],
            size_hint_x=None,
            width=80,
            halign="left",
            valign="middle",
        )
        search_label.bind(size=search_label.setter("text_size"))
        self.search_input = SearchInput(hint_text="Search games...")
        self.search_input.bind(text=self._on_search)
        search_bar.add_widget(search_label)
        search_bar.add_widget(self.search_input)

        self.scroll = ScrollView(size_hint=(1, 1))
        self.sections = BoxLayout(orientation="vertical", spacing=14, size_hint_y=None)
        self.sections.bind(minimum_height=self.sections.setter("height"))
        self.scroll.add_widget(self.sections)

        controls = BoxLayout(size_hint_y=None, height=44, spacing=8)
        rescan = Button(
            text="Rescan ROMs",
            size_hint=(None, 1),
            width=160,
            background_normal="",
            background_color=COLORS["panel_alt"],
            color=COLORS["text"],
        )
        rescan.bind(on_press=lambda *_: self._on_rescan_press())
        controls.add_widget(rescan)

        root.add_widget(header)
        root.add_widget(tab_bar)
        root.add_widget(search_bar)
        root.add_widget(self.scroll)
        root.add_widget(controls)
        self.add_widget(root)
        self.overlay = LoadingOverlay()

        self.state.bind(roms=self._rebuild_sections)
        self.state.bind(status_text=self._on_status)
        self.state.bind(rom_count=self._on_rom_count)
        self.state.bind(scan_in_progress=self._on_scan_state)
        self._on_scan_state()
        self._rebuild_sections()

    def _on_rom_count(self, *_):
        self.title.text = f"SuperConsole ({self.state.rom_count})"

    def _on_status(self, *_):
        self.status.text = self.state.status_text

    def _on_scan_state(self, *_):
        if self.state.scan_in_progress:
            self.overlay.show()
        else:
            self.overlay.hide()

    def _log_and_route(self, button_name: str, route: str) -> None:
        self.log.info("%s button pressed", button_name)
        set_route(self.state, route)

    def _on_rescan_press(self) -> None:
        self.log.info("Rescan ROMs button pressed")
        if self.on_rescan:
            self.on_rescan(force=True)

    def _on_search(self, _instance, value):
        self._search_text = value.strip()
        self._rebuild_sections()

    def _rebuild_sections(self, *_):
        self.sections.clear_widgets()
        games = list(self.state.roms)
        if self._search_text:
            filtered = [
                g for g in games
                if self._search_text.lower() in g.get("title", "").lower()
            ]
            header = SectionHeader("Search Results")
            self.sections.add_widget(header)
            if filtered:
                self.sections.add_widget(build_game_grid(filtered, on_select=self._on_game_press))
            else:
                empty = Label(
                    text="No matches.",
                    color=COLORS["muted"],
                    size_hint_y=None,
                    height=24,
                )
                self.sections.add_widget(empty)
            return

        if not games:
            empty = Label(
                text="No games found. Run a scan to build your library.",
                color=COLORS["muted"],
                size_hint_y=None,
                height=24,
            )
            self.sections.add_widget(empty)
            return

        recent = games[:10]
        recent_header = SectionHeader("Recently Added")
        self.sections.add_widget(recent_header)
        self.sections.add_widget(build_game_grid(recent, on_select=self._on_game_press))

        all_header = SectionHeader("All Games")
        self.sections.add_widget(all_header)
        self.sections.add_widget(build_game_grid(games, on_select=self._on_game_press))

    def _on_game_press(self, game: dict[str, str]) -> None:
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, "launch_game"):
            app.launch_game(game)
