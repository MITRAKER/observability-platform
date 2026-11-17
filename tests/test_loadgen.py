import asyncio
import random

import httpx
import pytest

from tests.conftest import mock_client


def test_defaults(loadgen):
    cfg = loadgen.load_config({})
    assert cfg.rps == 5.0
    assert cfg.total_requests == 5 * 86400


@pytest.mark.parametrize(
    "env",
    [{"RPS": "0"}, {"RPS": "1000"}, {"DURATION_S": "0"}, {"MAX_IN_FLIGHT": "0"}, {"MAX_IN_FLIGHT": "5000"}],
)
def test_rejects_out_of_range(loadgen, env):
    with pytest.raises(ValueError, match="must be within"):
        loadgen.load_config(env)


def test_random_checkout_is_valid(loadgen):
    rng = random.Random(1)
    for _ in range(100):
        body = loadgen.random_checkout(rng)
        assert 1 <= body["quantity"] <= 3
        assert body["unit_price"] > 0


def test_run_sends_exact_number_of_requests(loadgen, monkeypatch):
    calls = []

    def gateway(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(502 if len(calls) % 4 == 0 else 200)

    def network_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    offline = mock_client(network_error)  # built before httpx.AsyncClient is patched below
    clients = iter([mock_client(gateway)])
    monkeypatch.setattr(loadgen.httpx, "AsyncClient", lambda **_: next(clients))
    cfg = loadgen.Config(gateway_url="http://gw", rps=500, duration_s=0.04, max_in_flight=2)

    results = asyncio.run(loadgen.run(cfg, random.Random(0)))

    assert sum(results.values()) == cfg.total_requests == 20
    assert results[200] == 15
    assert results[502] == 5
    assert set(calls) == {"/checkout"}

    status = asyncio.run(loadgen.send_one(offline, "http://gw", {"item": "x"}))
    assert status == 0
