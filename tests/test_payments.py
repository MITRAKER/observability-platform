import pytest
from fastapi.testclient import TestClient

PAYMENT = {"order_id": "o1", "user_id": "u1", "amount": 10.0}


@pytest.fixture
def api(payments, monkeypatch):
    # No real waiting in tests.
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(payments.asyncio, "sleep", no_sleep)
    return TestClient(payments.app)


def test_health(api):
    assert api.get("/health").json() == {"status": "ok"}


def test_payment_approved_without_chaos(payments, api):
    api.post("/chaos", json={"error_rate": 0.0, "extra_latency_ms": 0})
    resp = api.post("/payments", json=PAYMENT)

    assert resp.status_code == 200
    assert resp.json() == {"order_id": "o1", "charged": 10.0, "status": "approved"}


def test_payment_fails_with_full_chaos(api):
    api.post("/chaos", json={"error_rate": 1.0, "extra_latency_ms": 0})
    assert api.post("/payments", json=PAYMENT).status_code == 500


def test_chaos_settings_round_trip(api):
    api.post("/chaos", json={"error_rate": 0.3, "extra_latency_ms": 200})
    assert api.get("/chaos").json() == {"error_rate": 0.3, "extra_latency_ms": 200}


@pytest.mark.parametrize(
    "settings",
    [{"error_rate": 1.5, "extra_latency_ms": 0}, {"error_rate": 0.1, "extra_latency_ms": -1}],
)
def test_chaos_rejects_out_of_range(api, settings):
    assert api.post("/chaos", json=settings).status_code == 422


def test_payment_rejects_non_positive_amount(api):
    assert api.post("/payments", json={**PAYMENT, "amount": 0}).status_code == 422


@pytest.mark.parametrize(("rate", "roll", "fails"), [(0.0, 0.0, False), (0.5, 0.49, True), (0.5, 0.5, False)])
def test_should_fail_boundaries(payments, rate, roll, fails):
    assert payments.should_fail(rate, roll) is fails


def test_settings_from_env(payments, monkeypatch):
    monkeypatch.setenv("CHAOS_ERROR_RATE", "0.25")
    monkeypatch.setenv("CHAOS_EXTRA_LATENCY_MS", "40")
    assert payments.settings_from_env().model_dump() == {"error_rate": 0.25, "extra_latency_ms": 40}


def test_settings_from_env_rejects_bad_values(payments, monkeypatch):
    monkeypatch.setenv("CHAOS_ERROR_RATE", "2")
    with pytest.raises(ValueError, match="error_rate"):
        payments.settings_from_env()
