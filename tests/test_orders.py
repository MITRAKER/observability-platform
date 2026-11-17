import json

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import mock_client

GOOD = {"user_id": "u1", "item": "mouse", "quantity": 2, "unit_price": 19.5}


def payments_answering(status: int):
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["amount"] == 39.0
        return httpx.Response(status, json={"status": "approved" if status == 200 else "error"})

    return handler


def test_health(orders):
    assert TestClient(orders.app).get("/health").json() == {"status": "ok"}


def test_paid_order_is_stored_and_readable(orders, monkeypatch):
    monkeypatch.setattr(orders, "client", mock_client(payments_answering(200)))
    api = TestClient(orders.app)

    order = api.post("/orders", json=GOOD).json()

    assert order["status"] == "paid"
    assert order["amount"] == 39.0
    assert api.get(f"/orders/{order['order_id']}").json() == order


def test_failed_payment_returns_502(orders, monkeypatch):
    monkeypatch.setattr(orders, "client", mock_client(payments_answering(500)))
    resp = TestClient(orders.app).post("/orders", json=GOOD)

    assert resp.status_code == 502
    assert len(orders.ORDERS) == 1


def test_unreachable_payments_returns_503(orders, monkeypatch):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    monkeypatch.setattr(orders, "client", mock_client(down))
    assert TestClient(orders.app).post("/orders", json=GOOD).status_code == 503


def test_unknown_order_is_404(orders):
    assert TestClient(orders.app).get("/orders/nope").status_code == 404


def test_price_order_rounds_to_cents(orders):
    req = orders.OrderRequest(user_id="u", item="cable", quantity=3, unit_price=7.255)
    assert orders.price_order("o1", req) == 21.77


def test_bounded_store_evicts_oldest(orders):
    store = orders.BoundedStore(capacity=2)
    store.put("a", {"n": 1})
    store.put("b", {"n": 2})
    store.put("c", {"n": 3})

    assert len(store) == 2
    assert store.get("a") is None
    assert store.get("c") == {"n": 3}


def test_bounded_store_refreshes_existing_key(orders):
    store = orders.BoundedStore(capacity=2)
    store.put("a", {"n": 1})
    store.put("b", {"n": 2})
    store.put("a", {"n": 10})
    store.put("c", {"n": 3})

    assert store.get("a") == {"n": 10}
    assert store.get("b") is None


def test_bounded_store_rejects_zero_capacity(orders):
    with pytest.raises(ValueError, match="positive"):
        orders.BoundedStore(capacity=0)


def test_price_order_enforces_positive_invariant(orders):
    # model_construct skips validation, simulating a bug upstream.
    req = orders.OrderRequest.model_construct(user_id="u", item="x", quantity=0, unit_price=1.0)
    with pytest.raises(ValueError, match="non-positive"):
        orders.price_order("o1", req)
