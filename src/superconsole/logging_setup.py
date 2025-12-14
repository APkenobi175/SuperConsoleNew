import logging

def setup_logging(level: int = logging.INFO) -> None:
    """Sets up logging configuration for the application."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

