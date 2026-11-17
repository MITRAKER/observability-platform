"""A tiny webhook receiver that prints Alertmanager notifications.

It stands in for Slack or PagerDuty so the demo needs no accounts. Only the
Python standard library is used, so the image needs no pip install.
"""
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

MAX_BODY_BYTES = 1_000_000  # refuse absurdly large payloads (bounded input)
PORT = 9000

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("alert-sink")


def describe(alert: dict) -> str:
    """Return a one-line, human-readable summary of one alert."""
    labels = alert.get("labels", {})
    notes = alert.get("annotations", {})
    status = alert.get("status", "unknown").upper()
    name = labels.get("alertname", "?")
    severity = labels.get("severity", "none")
    return f"[{status}] {name} ({severity}): {notes.get('summary', '')}"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (name required by BaseHTTPRequestHandler)
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_response(413)
            self.end_headers()
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        for alert in payload.get("alerts", [])[:100]:  # bounded loop
            log.info(describe(alert))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return  # silence the default per-request access log


if __name__ == "__main__":
    log.info("alert-sink listening on :%d", PORT)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
