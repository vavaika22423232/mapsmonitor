"""
Simple in-memory metrics for observability.
Logged periodically or at shutdown.
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Application metrics counters."""

    events_parsed: int = 0
    events_sent: int = 0
    geocode_cache_hit: int = 0
    geocode_api_called: int = 0

    def log(self) -> None:
        """Log aggregated metrics."""
        logger.info(
            "metrics events_parsed=%d events_sent=%d geocode_cache_hit=%d geocode_api_called=%d",
            self.events_parsed,
            self.events_sent,
            self.geocode_cache_hit,
            self.geocode_api_called,
        )


_metrics = Metrics()


def get_metrics() -> Metrics:
    return _metrics
