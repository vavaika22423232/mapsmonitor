"""
Logging configuration utilities.
"""
import json
import logging
import os


class JsonFormatter(logging.Formatter):
    """JSON format for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        if record.name:
            log_obj["logger"] = record.name
        if hasattr(record, "channel"):
            log_obj["channel"] = record.channel
        if hasattr(record, "event_id"):
            log_obj["event_id"] = record.event_id
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging for the application."""
    log_format = os.environ.get("LOG_FORMAT", "default")
    if log_format == "json":
        for h in logging.root.handlers[:]:
            logging.root.removeHandler(h)
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logging.root.addHandler(handler)
        logging.root.setLevel(level)
    else:
        logging.basicConfig(
            format="[%(levelname)s/%(asctime)s] %(message)s",
            level=level,
        )
