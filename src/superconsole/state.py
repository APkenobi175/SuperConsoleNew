from __future__ import annotations
from kivy.event import EventDispatcher
from kivy.properties import (
    StringProperty, NumericProperty, BooleanProperty, ListProperty
)
# Define states used in the application
class AppState(EventDispatcher):
    route = StringProperty("home") # possible routes for pages.
    status_text = StringProperty("Ready") # status bar text
    scan_in_progress = BooleanProperty(False) # if a scan is in progress
    rom_count = NumericProperty(0) # how many ROMs are known

    # Keep it simple for now: list of strings (paths or names).
    # Later this becomes a list of Game objects.
    roms = ListProperty([]) # list of roms
