# What this does is define actions that modify the state of the application

from __future__ import annotations
from .state import AppState

def set_route(state: AppState, route: str) -> None:
    state.route = route

def set_status(state: AppState, text: str) -> None:
    state.status_text = text
