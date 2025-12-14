from __future__ import annotations
import logging

from .logging_setup import setup_logging
from .validate import validate_or_raise
from .state import AppState
from .ui.app import SuperConsoleApp

def main() -> int:
    setup_logging(logging.INFO)
    validate_or_raise()

    state = AppState()
    SuperConsoleApp(state=state).run()
    return 0
