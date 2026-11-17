"""Sends a steady stream of checkout requests to the gateway.

Without traffic, every dashboard is empty. This script is the "users".

Settings (environment variables):
  GATEWAY_URL       where to send requests       (default http://gateway:8000)
  RPS               requests per second, 0.1-500 (default 5)
  DURATION_S        stop after this many seconds (default 86400 = one day)
  MAX_IN_FLIGHT     cap on concurrent requests   (default 50)

Both loops are bounded (JPL rule 2): the run stops after DURATION_S, and at
most MAX_IN_FLIGHT requests are open at once. Docker restarts the container
when it exits.
"""

import asyncio
import os
import random
from collections import Counter
from dataclasses import dataclass

import httpx

ITEMS = (("keyboard", 49.0), ("mouse", 19.5), ("monitor", 189.0), ("cable", 7.25))
MAX_USERS = 50
RPS_RANGE = (0.1, 500.0)
DURATION_RANGE_S = (1.0, 7 * 86400.0)
IN_FLIGHT_RANGE = (1, 1000)


@dataclass(frozen=True)
class Config:
    """Validated load generator settings."""

    gateway_url: str
    rps: float
    duration_s: float
    max_in_flight: int

    @property
    def total_requests(self) -> int:
        """Upper bound on how many requests one run sends."""
        return int(self.rps * self.duration_s)


def load_config(env: dict[str, str]) -> Config:
    """Build a Config from environment variables, rejecting out-of-range values."""
    cfg = Config(
        gateway_url=env.get("GATEWAY_URL", "http://gateway:8000"),
        rps=float(env.get("RPS", "5")),
        duration_s=float(env.get("DURATION_S", "86400")),
        max_in_flight=int(env.get("MAX_IN_FLIGHT", "50")),
    )
    if not RPS_RANGE[0] <= cfg.rps <= RPS_RANGE[1]:
        raise ValueError(f"RPS must be within {RPS_RANGE}, got {cfg.rps}")
    if not DURATION_RANGE_S[0] <= cfg.duration_s <= DURATION_RANGE_S[1]:
        raise ValueError(f"DURATION_S must be within {DURATION_RANGE_S}, got {cfg.duration_s}")
    if not IN_FLIGHT_RANGE[0] <= cfg.max_in_flight <= IN_FLIGHT_RANGE[1]:
        raise ValueError(f"MAX_IN_FLIGHT must be within {IN_FLIGHT_RANGE}, got {cfg.max_in_flight}")
    return cfg


def random_checkout(rng: random.Random) -> dict[str, str | int | float]:
    """Return one random, valid checkout body."""
    item, price = rng.choice(ITEMS)
    return {
        "user_id": f"user-{rng.randint(1, MAX_USERS)}",
        "item": item,
        "quantity": rng.randint(1, 3),
        "unit_price": price,
    }


async def send_one(client: httpx.AsyncClient, url: str, body: dict[str, str | int | float]) -> int:
    """Send one checkout. Returns the HTTP status, or 0 on a network error."""
    try:
        resp = await client.post(f"{url}/checkout", json=body)
    except httpx.RequestError as exc:
        print("ERR", exc, flush=True)
        return 0
    print(resp.status_code, body["item"], flush=True)
    return resp.status_code


async def run(cfg: Config, rng: random.Random) -> Counter[int]:
    """Send cfg.total_requests requests at cfg.rps; return a count per status.

    Memory stays bounded: at most cfg.max_in_flight tasks exist at once, and
    results are folded into a small Counter instead of a growing list.
    """
    slots = asyncio.Semaphore(cfg.max_in_flight)
    results: Counter[int] = Counter()
    pending: set[asyncio.Task[int]] = set()

    def finished(task: asyncio.Task[int]) -> None:
        pending.discard(task)
        slots.release()
        results[task.result()] += 1

    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(cfg.total_requests):  # bounded loop
            await slots.acquire()  # back-pressure: wait if too many are open
            task = asyncio.create_task(send_one(client, cfg.gateway_url, random_checkout(rng)))
            pending.add(task)
            task.add_done_callback(finished)
            await asyncio.sleep(1 / cfg.rps)
        await asyncio.gather(*pending)
    return results


if __name__ == "__main__":
    asyncio.run(run(load_config(dict(os.environ)), random.Random()))  # noqa: S311
