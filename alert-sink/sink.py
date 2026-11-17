"""A tiny webhook receiver that prints Alertmanager notifications.

It stands in for Slack or PagerDuty so the demo needs no accounts. Only the
Python standard library is used, so the image needs no pip install.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

MAX_BODY_BYTES = 1_000_000  # refuse absurdly large payloads (bounded input)
MAX_ALERTS_PER_MESSAGE = 100  # bounded loop over the payload
MAX_FIELD_CHARS = 200  # longest value we copy from a payload into a log line
HOST = "0.0.0.0"  # noqa: S104 (runs in a container; must accept connections from Alertmanager)
PORT = 9000

log = logging.getLogger("alert-sink")


def clean(value: object) -> str:
    """Make an untrusted value safe for a single log line.

    Line breaks and other control characters are replaced, so a crafted
    payload cannot forge extra log lines (log injection), and the length is
    capped.
    """
    text = str(value)[:MAX_FIELD_CHARS]
    return "".join(ch if ch.isprintable() else " " for ch in text)


def describe(alert: dict[str, Any]) -> str:
    """Return a one-line, human-readable summary of one alert."""
    labels = alert.get("labels", {})
    notes = alert.get("annotations", {})
    status = clean(alert.get("status", "unknown")).upper()
    name = clean(labels.get("alertname", "?"))
    severity = clean(labels.get("severity", "none"))
    return f"[{status}] {name} ({severity}): {clean(notes.get('summary', ''))}"


def parse_payload(raw: bytes) -> list[dict[str, Any]] | None:
    """Return the alerts in an Alertmanager webhook body, or None if malformed."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
        return None
    return [a for a in payload["alerts"][:MAX_ALERTS_PER_MESSAGE] if isinstance(a, dict)]


class Handler(BaseHTTPRequestHandler):
    """Handles POST requests from Alertmanager."""

    def do_POST(self) -> None:
        """Log each alert in the request body and answer 200, or 4xx if invalid."""
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_response(413)
            self.end_headers()
            return
        alerts = parse_payload(self.rfile.read(length))
        if alerts is None:
            self.send_response(400)
            self.end_headers()
            return
        for alert in alerts:  # bounded by MAX_ALERTS_PER_MESSAGE
            log.info(describe(alert))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # signature fixed by the base class
        """Silence the default per-request access log."""


def main() -> None:
    """Start the HTTP server and serve until the container stops."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    log.info("alert-sink listening on :%d", PORT)
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
