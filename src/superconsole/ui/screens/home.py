from __future__ import annotations
import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Line

from ...actions import set_route
from ..widgets import (
    COLORS,
    apply_bg,
    SectionHeader,
    LoadingOverlay,
    build_game_grid,
    HoverButton,
)

class HomeScreen(Screen):
    def __init__(self, state, on_rescan=None, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.on_rescan = on_rescan
        self.log = logging.getLogger(__name__)
        self.nav_bar = None

        root = BoxLayout(orientation="vertical", padding=16, spacing=10)
        apply_bg(root, COLORS["bg"])

        header = BoxLayout(size_hint_y=None, height=48, padding=[12, 6], spacing=8)
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

        nav_frame = BoxLayout(size_hint_y=None, height=48, padding=[6, 6])
        apply_bg(nav_frame, COLORS["panel_alt"])
        with nav_frame.canvas.after:
            Color(*COLORS["border"])
            self._nav_line = Line(points=[nav_frame.x, nav_frame.y, nav_frame.right, nav_frame.y], width=1.0)
        nav_frame.bind(
            pos=lambda *_: self._sync_nav_line(nav_frame),
            size=lambda *_: self._sync_nav_line(nav_frame),
        )

        nav_scroll = ScrollView(size_hint_y=None, height=44, do_scroll_y=False)
        nav_scroll.bar_width = 6
        nav_scroll.bar_color = (*COLORS["accent"][:3], 0.6)
        nav_scroll.bar_inactive_color = (*COLORS["accent"][:3], 0.2)
        self.nav_bar = BoxLayout(size_hint=(None, 1), spacing=8, padding=[2, 2])
        self.nav_bar.bind(minimum_width=self.nav_bar.setter("width"))
        nav_scroll.add_widget(self.nav_bar)
        nav_frame.add_widget(nav_scroll)
        self._rebuild_nav()

        self.scroll = ScrollView(size_hint=(1, 1))
        self.sections = BoxLayout(orientation="vertical", spacing=14, size_hint_y=None)
        self.sections.bind(minimum_height=self.sections.setter("height"))
        self.scroll.add_widget(self.sections)

        controls = BoxLayout(size_hint_y=None, height=44, spacing=8)
        rescan = HoverButton(
            text="Rescan ROMs",
            size_hint=(None, 1),
            width=160,
            color=COLORS["text"],
            base_color=COLORS["panel_alt"],
            hover_color=COLORS["accent"],
        )
        rescan.bind(on_press=lambda *_: self._on_rescan_press())
        controls.add_widget(rescan)

        root.add_widget(header)
        root.add_widget(nav_frame)
        root.add_widget(self.scroll)
        root.add_widget(controls)
        self.add_widget(root)
        self.overlay = LoadingOverlay()

        self.state.bind(favorites=self._rebuild_sections)
        self.state.bind(recent_played=self._rebuild_sections)
        self.state.bind(recent_added=self._rebuild_sections)
        self.state.bind(status_text=self._on_status)
        self.state.bind(rom_count=self._on_rom_count)
        self.state.bind(scan_in_progress=self._on_scan_state)
        self.state.bind(platforms=self._rebuild_nav)
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

    def _rebuild_sections(self, *_):
        self.sections.clear_widgets()
        favorites = list(self.state.favorites)
        recent_played = list(self.state.recent_played)
        recent_added = list(self.state.recent_added)

        if not favorites and not recent_played and not recent_added:
            empty = Label(
                text="No games found. Run a scan to build your library.",
                color=COLORS["muted"],
                size_hint_y=None,
                height=24,
            )
            self.sections.add_widget(empty)
            return

        if favorites:
            fav_header = SectionHeader("Favorites")
            self.sections.add_widget(fav_header)
            self.sections.add_widget(build_game_grid(favorites, on_select=self._on_game_press))

        if recent_played:
            played_header = SectionHeader("Recently Played")
            self.sections.add_widget(played_header)
            self.sections.add_widget(build_game_grid(recent_played, on_select=self._on_game_press))

        if recent_added:
            added_header = SectionHeader("Recently Added")
            self.sections.add_widget(added_header)
            self.sections.add_widget(build_game_grid(recent_added, on_select=self._on_game_press))

    def _on_game_press(self, game: dict[str, str]) -> None:
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, "launch_game"):
            app.launch_game(game)

    def _rebuild_nav(self, *_):
        if not self.nav_bar:
            return
        self.nav_bar.clear_widgets()

        home_btn = HoverButton(
            text="Home",
            size_hint=(None, 1),
            width=110,
            color=COLORS["text"],
            base_color=COLORS["accent"],
            hover_color=COLORS["tab_active"],
        )
        home_btn.bind(on_press=lambda *_: self._log_and_route("Home", "home"))
        self.nav_bar.add_widget(home_btn)

        for platform in self.state.platforms:
            btn = HoverButton(
                text=platform.title(),
                size_hint=(None, 1),
                width=110,
                color=COLORS["text"],
                base_color=COLORS["panel"],
                hover_color=COLORS["tab_active"],
            )
            btn.bind(on_press=lambda _b, p=platform: self._log_and_route(p, f"platform:{p}"))
            self.nav_bar.add_widget(btn)

    def _sync_nav_line(self, nav_frame):
        self._nav_line.points = [nav_frame.x, nav_frame.y, nav_frame.right, nav_frame.y]
