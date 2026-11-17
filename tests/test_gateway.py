import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import mock_client

GOOD = {"user_id": "u1", "item": "mouse", "quantity": 2, "unit_price": 19.5}


def test_health(gateway):
    assert TestClient(gateway.app).get("/health").json() == {"status": "ok"}


def test_checkout_forwards_to_orders(gateway, monkeypatch):
    seen = []

    def orders(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"order_id": "o1", "status": "paid"})

    monkeypatch.setattr(gateway, "client", mock_client(orders))
    resp = TestClient(gateway.app).post("/checkout", json=GOOD)

    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"
    assert seen[0].url.path == "/orders"


@pytest.mark.parametrize(
    "body",
    [
        {**GOOD, "quantity": 0},
        {**GOOD, "quantity": 11},
        {**GOOD, "unit_price": -1},
        {**GOOD, "user_id": ""},
        {"item": "mouse"},
    ],
)
def test_checkout_rejects_invalid_input(gateway, body):
    assert TestClient(gateway.app).post("/checkout", json=body).status_code == 422


def test_checkout_passes_downstream_error_through(gateway, monkeypatch):
    def orders(_: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"detail": "payment failed"})

    monkeypatch.setattr(gateway, "client", mock_client(orders))
    resp = TestClient(gateway.app).post("/checkout", json=GOOD)

    assert resp.status_code == 502
    assert resp.json()["detail"] == "payment failed"


def test_checkout_returns_503_when_orders_unreachable(gateway, monkeypatch):
    def orders(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(gateway, "client", mock_client(orders))
    resp = TestClient(gateway.app).post("/checkout", json=GOOD)

    assert resp.status_code == 503


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(500, json={"detail": "boom"}), "boom"),
        (httpx.Response(500, json={"detail": 42}), "downstream error"),
        (httpx.Response(500, json=["not", "a", "dict"]), "downstream error"),
        (httpx.Response(500, text="plain text"), "plain text"),
        (httpx.Response(500, text=""), "downstream error"),
    ],
)
def test_error_detail_handles_any_body(gateway, response, expected):
    assert gateway.error_detail(response) == expected
