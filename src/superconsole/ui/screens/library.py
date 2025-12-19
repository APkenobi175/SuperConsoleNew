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
    SearchInput,
    LoadingOverlay,
    build_game_grid,
    HoverButton,
)

class LibraryScreen(Screen):
    def __init__(self, state, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self._search_text = ""
        self.log = logging.getLogger(__name__)
        self.nav_bar = None

        root = BoxLayout(orientation="vertical", padding=16, spacing=10)
        apply_bg(root, COLORS["bg"])

        header = BoxLayout(size_hint_y=None, height=44, padding=[10, 6], spacing=8)
        apply_bg(header, COLORS["panel"])
        self.title = Label(
            text="Library",
            font_size="20sp",
            color=COLORS["text"],
            bold=True,
            halign="left",
            valign="middle",
        )
        self.title.bind(size=self.title.setter("text_size"))
        self.count = Label(
            text="0 games",
            font_size="12sp",
            color=COLORS["muted"],
            halign="right",
            valign="middle",
        )
        self.count.bind(size=self.count.setter("text_size"))
        header.add_widget(self.title)
        header.add_widget(self.count)

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

        root.add_widget(header)
        root.add_widget(nav_frame)
        root.add_widget(search_bar)
        root.add_widget(self.scroll)
        self.add_widget(root)
        self.overlay = LoadingOverlay()

        self.state.bind(current_games=self._rebuild_sections)
        self.state.bind(current_platform=self._update_title)
        self.state.bind(platforms=self._rebuild_nav)
        self.state.bind(scan_in_progress=self._on_scan_state)
        self._on_scan_state()
        self._rebuild_sections()
        self._update_title()

    def _on_search(self, _instance, value):
        self._search_text = value.strip()
        self._rebuild_sections()

    def _rebuild_sections(self, *_):
        self.sections.clear_widgets()
        games = list(self.state.current_games)
        self.count.text = f"{len(games)} games"

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
                text="No games found.",
                color=COLORS["muted"],
                size_hint_y=None,
                height=24,
            )
            self.sections.add_widget(empty)
            return

        header = SectionHeader("All Games")
        self.sections.add_widget(header)
        self.sections.add_widget(build_game_grid(games, on_select=self._on_game_press))

    def _on_game_press(self, game: dict[str, str]) -> None:
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, "launch_game"):
            app.launch_game(game)

    def _on_scan_state(self, *_):
        if self.state.scan_in_progress:
            self.overlay.show()
        else:
            self.overlay.hide()

    def _log_and_route(self, button_name: str, route: str) -> None:
        self.log.info("%s button pressed", button_name)
        set_route(self.state, route)

    def _update_title(self, *_):
        platform = self.state.current_platform or "Library"
        self.title.text = platform.upper()

    def _rebuild_nav(self, *_):
        if not self.nav_bar:
            return
        self.nav_bar.clear_widgets()

        home_btn = HoverButton(
            text="Home",
            size_hint=(None, 1),
            width=110,
            color=COLORS["text"],
            base_color=COLORS["panel"],
            hover_color=COLORS["tab_active"],
        )
        home_btn.bind(on_press=lambda *_: self._log_and_route("Home", "home"))
        self.nav_bar.add_widget(home_btn)

        for platform in self.state.platforms:
            is_active = platform == self.state.current_platform
            btn = HoverButton(
                text=platform.title(),
                size_hint=(None, 1),
                width=110,
                color=COLORS["text"],
                base_color=COLORS["accent"] if is_active else COLORS["panel"],
                hover_color=COLORS["tab_active"],
            )
            btn.bind(on_press=lambda _b, p=platform: self._log_and_route(p, f"platform:{p}"))
            self.nav_bar.add_widget(btn)

    def _sync_nav_line(self, nav_frame):
        self._nav_line.points = [nav_frame.x, nav_frame.y, nav_frame.right, nav_frame.y]
