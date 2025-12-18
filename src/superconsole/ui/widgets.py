from __future__ import annotations

from kivy.graphics import Color, Rectangle, Line, PushMatrix, PopMatrix, Rotate
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.animation import Animation
from kivy.properties import NumericProperty
from kivy.uix.modalview import ModalView


CARD_HEIGHT = 230

COLORS = {
    "bg": get_color_from_hex("#1b2838"),
    "panel": get_color_from_hex("#22344a"),
    "panel_alt": get_color_from_hex("#2a475e"),
    "tab_idle": get_color_from_hex("#1f2e3d"),
    "tab_active": get_color_from_hex("#2a475e"),
    "card": get_color_from_hex("#22354a"),
    "cover": get_color_from_hex("#2f4f67"),
    "border": get_color_from_hex("#31495e"),
    "text": get_color_from_hex("#ffffff"),
    "muted": get_color_from_hex("#a7b2bf"),
    "accent": get_color_from_hex("#3a6ea5"),
}


def apply_bg(widget, color):
    with widget.canvas.before:
        bg_color = Color(*color)
        bg_rect = Rectangle(pos=widget.pos, size=widget.size)

    def _sync_bg(*_):
        bg_rect.pos = widget.pos
        bg_rect.size = widget.size

    widget.bind(pos=_sync_bg, size=_sync_bg)
    return bg_color, bg_rect


class TabButton(ButtonBehavior, BoxLayout):
    def __init__(self, text: str, **kwargs):
        super().__init__(
            orientation="horizontal",
            padding=[12, 6],
            size_hint=(None, 1),
            width=140,
            **kwargs,
        )
        with self.canvas.before:
            self._bg_color = Color(*COLORS["tab_idle"])
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            self._border = Line(rectangle=(self.x, self.y, self.width, self.height), width=1.0)

        self.label = Label(
            text=text,
            color=COLORS["text"],
            bold=True,
            halign="center",
            valign="middle",
        )
        self.label.bind(size=self.label.setter("text_size"))
        self.add_widget(self.label)
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)

    def _sync_canvas(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border.rectangle = (self.x, self.y, self.width, self.height)

    def set_active(self, active: bool) -> None:
        self._bg_color.rgba = COLORS["tab_active"] if active else COLORS["tab_idle"]


class GameCard(ButtonBehavior, BoxLayout):
    def __init__(self, title: str, cover_source: str, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint=(1, None),
            height=CARD_HEIGHT,
            padding=8,
            spacing=6,
            **kwargs,
        )
        with self.canvas.before:
            self._bg_color = Color(*COLORS["card"])
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            self._border = Line(rectangle=(self.x, self.y, self.width, self.height), width=1.0)

        self.cover = BoxLayout(size_hint=(1, 0.78))
        apply_bg(self.cover, COLORS["cover"])
        self.cover_image = KivyImage(
            source=cover_source,
            allow_stretch=True,
            keep_ratio=True,
        )
        self.cover.add_widget(self.cover_image)

        self.title = Label(
            text=title,
            color=COLORS["text"],
            font_size="14sp",
            size_hint_y=None,
            height=28,
            halign="center",
            valign="middle",
            shorten=True,
            shorten_from="right",
        )
        self.title.bind(size=self.title.setter("text_size"))

        self.add_widget(self.cover)
        self.add_widget(self.title)
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)

    def _sync_canvas(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border.rectangle = (self.x, self.y, self.width, self.height)


class SectionHeader(BoxLayout):
    def __init__(self, text: str, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=28,
            padding=[4, 0],
            **kwargs,
        )
        self.label = Label(
            text=text,
            color=COLORS["text"],
            bold=True,
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        self.label.bind(size=self.label.setter("text_size"))
        self.add_widget(self.label)
        with self.canvas.after:
            self._line_color = Color(*COLORS["border"])
            self._line = Line(points=[self.x, self.y, self.right, self.y], width=1.0)
        self.bind(pos=self._sync_line, size=self._sync_line)

    def _sync_line(self, *_):
        self._line.points = [self.x, self.y, self.right, self.y]


class SearchInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(
            multiline=False,
            background_normal="",
            background_active="",
            background_color=COLORS["panel"],
            foreground_color=COLORS["text"],
            cursor_color=COLORS["accent"],
            padding=[10, 10, 10, 10],
            **kwargs,
        )


class LoadingSpinner(Widget):
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        if "size_hint" not in kwargs:
            kwargs["size_hint"] = (None, None)
        if "size" not in kwargs:
            kwargs["size"] = (20, 20)
        super().__init__(**kwargs)
        with self.canvas:
            PushMatrix()
            self._rot = Rotate(angle=self.angle, origin=self.center)
            Color(*COLORS["accent"])
            self._line = Line(circle=(self.center_x, self.center_y, 8, 0, 270), width=2)
            PopMatrix()
        self.bind(pos=self._sync, size=self._sync, angle=self._sync_angle)
        self._anim = Animation(angle=360, duration=0.9)
        self._anim += Animation(angle=0, duration=0)
        self._anim.repeat = True

    def _sync(self, *_):
        self._rot.origin = self.center
        self._line.circle = (self.center_x, self.center_y, min(self.width, self.height) / 2.5, 0, 270)

    def _sync_angle(self, *_):
        self._rot.angle = self.angle

    def start(self):
        self._anim.start(self)

    def stop(self):
        self._anim.cancel(self)


class LoadingOverlay(ModalView):
    def __init__(self, text: str = "Scanning library...", **kwargs):
        kwargs.setdefault("auto_dismiss", False)
        kwargs.setdefault("background", "")
        kwargs.setdefault("background_color", (0, 0, 0, 0.55))
        super().__init__(**kwargs)

        container = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            width=220,
            height=120,
            spacing=8,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        apply_bg(container, COLORS["panel"])

        self.spinner = LoadingSpinner(size=(32, 32))
        label = Label(
            text=text,
            color=COLORS["text"],
            font_size="14sp",
            halign="center",
            valign="middle",
        )
        label.bind(size=label.setter("text_size"))
        container.add_widget(self.spinner)
        container.add_widget(label)
        self.add_widget(container)

    def show(self):
        if self.parent is None:
            self.open()
        self.spinner.start()

    def hide(self):
        self.spinner.stop()
        if self.parent is not None:
            self.dismiss()


def build_game_grid(items: list[dict[str, str]], cols: int = 5) -> GridLayout:
    grid = GridLayout(
        cols=cols,
        spacing=12,
        padding=[10, 8],
        size_hint_y=None,
        row_force_default=True,
        row_default_height=CARD_HEIGHT,
    )
    grid.bind(minimum_height=grid.setter("height"))
    for item in items:
        grid.add_widget(GameCard(item.get("title", ""), item.get("cover_path", "")))
    return grid
