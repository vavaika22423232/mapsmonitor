"""
Health check HTTP server for Render and other platforms.
Runs in a background thread when HEALTH_CHECK_PORT is set.
"""
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)


def _make_handler():
    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            logger.debug("Health check: %s", args[0] if args else "")

        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()

    return HealthHandler


def start_health_server(port: int) -> threading.Thread:
    """Start health check HTTP server in a daemon thread."""
    server = HTTPServer(("0.0.0.0", port), _make_handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server listening on port %d", port)
    return thread


def maybe_start_health_server() -> bool:
    """Start health server if HEALTH_CHECK_PORT is set. Returns True if started."""
    port_str = os.environ.get("HEALTH_CHECK_PORT")
    if not port_str:
        return False
    try:
        port = int(port_str)
        start_health_server(port)
        return True
    except ValueError:
        logger.warning("HEALTH_CHECK_PORT must be an integer, got %r", port_str)
        return False
