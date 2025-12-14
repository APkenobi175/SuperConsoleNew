from __future__ import annotations
import logging

from .logging_setup import setup_logging
from .validate import validate_or_raise
from .ui.app import SuperConsoleApp


def main() -> int:
    setup_logging(logging.INFO)

    result = validate_or_raise()

    # Minimal “boot test” UI
    SuperConsoleApp(rom_count=result.rom_count).run()
    return 0