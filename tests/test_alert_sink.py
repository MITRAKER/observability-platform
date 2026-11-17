import io
import json
import logging

ALERT = {
    "status": "firing",
    "labels": {"alertname": "CheckoutErrorBudgetFastBurn", "severity": "page"},
    "annotations": {"summary": "Checkout is burning its error budget"},
}


def test_describe(sink):
    line = sink.describe(ALERT)
    assert line == "[FIRING] CheckoutErrorBudgetFastBurn (page): Checkout is burning its error budget"


def test_describe_tolerates_missing_fields(sink):
    assert sink.describe({}) == "[UNKNOWN] ? (none): "


def test_parse_payload(sink):
    assert sink.parse_payload(json.dumps({"alerts": [ALERT, "junk"]}).encode()) == [ALERT]
    assert sink.parse_payload(b"not json") is None
    assert sink.parse_payload(b"[1, 2]") is None
    assert sink.parse_payload(b'{"alerts": "nope"}') is None


def test_parse_payload_is_bounded(sink):
    many = json.dumps({"alerts": [ALERT] * 1000}).encode()
    assert len(sink.parse_payload(many)) == sink.MAX_ALERTS_PER_MESSAGE


class FakeHandler:
    """Drives sink.Handler.do_POST without opening a socket."""

    def __init__(self, sink, body: bytes, length: int | None = None):
        self.headers = {"Content-Length": str(len(body) if length is None else length)}
        self.rfile = io.BytesIO(body)
        self.status: int | None = None
        self.post = sink.Handler.do_POST

    def send_response(self, code: int) -> None:
        self.status = code

    def end_headers(self) -> None:
        return None


def post(sink, body: bytes, length: int | None = None) -> int | None:
    handler = FakeHandler(sink, body, length)
    handler.post(handler)
    return handler.status


def test_handler_status_codes(sink, caplog):
    with caplog.at_level(logging.INFO, logger="alert-sink"):
        assert post(sink, json.dumps({"alerts": [ALERT]}).encode()) == 200
    assert "CheckoutErrorBudgetFastBurn" in caplog.text
    assert post(sink, b"{bad") == 400
    assert post(sink, b"", length=0) == 413
    assert post(sink, b"x", length=sink.MAX_BODY_BYTES + 1) == 413


def test_describe_blocks_log_injection(sink):
    forged = {
        "status": "firing",
        "labels": {"alertname": "X\n[RESOLVED] FakeAlert (page): all good", "severity": "page"},
        "annotations": {"summary": "a" * 1000},
    }
    line = sink.describe(forged)
    assert "\n" not in line
    assert "X [RESOLVED] FakeAlert" in line
    assert len(line) < 500
