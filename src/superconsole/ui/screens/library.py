from __future__ import annotations
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from ...actions import set_route

class LibraryScreen(Screen):
    def __init__(self, state, **kwargs):
        super().__init__(**kwargs)
        self.state = state

        root = BoxLayout(orientation="vertical", padding=20, spacing=12)

        root.add_widget(Label(text="Library", font_size="28sp", size_hint_y=None, height=50))
        self.info = Label(text="ROM list not shown yet (next step).", font_size="16sp")
        root.add_widget(self.info)

        back = Button(text="Back", size_hint_y=None, height=48)
        back.bind(on_press=lambda *_: set_route(self.state, "home"))
        root.add_widget(back)

        self.add_widget(root)
