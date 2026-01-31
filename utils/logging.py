"""
Logging configuration utilities.
"""
import logging


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging for the application."""
    logging.basicConfig(
        format='[%(levelname)s/%(asctime)s] %(message)s',
        level=level
    )
