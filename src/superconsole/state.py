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

    # List of dicts like {"title": str, "cover_path": str, "platform": str, "launch_target": str, "launch_type": str}
    roms = ListProperty([]) # list of roms
