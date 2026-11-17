"""Payments: pretends to charge a card.

Two environment variables turn on "chaos" so the dashboards and alerts have
something to show:
  CHAOS_ERROR_RATE        share of requests that fail, 0.0 to 1.0 (default 0.02)
  CHAOS_EXTRA_LATENCY_MS  extra delay added to every request, 0 to 10000 (default 0)
You can also change them while the service runs with POST /chaos.
"""

import asyncio
import logging
import os
import random

from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel, Field

MAX_EXTRA_LATENCY_MS = 10_000
BASE_LATENCY_MS = (20.0, 120.0)

log = logging.getLogger("payments")
tracer = trace.get_tracer("payments")
app = FastAPI(title="payments")


class PaymentRequest(BaseModel):
    """Body of POST /payments, as sent by the orders service."""

    order_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0)


class ChaosSettings(BaseModel):
    """Failure injection settings. Pydantic enforces the bounds."""

    error_rate: float = Field(ge=0.0, le=1.0)
    extra_latency_ms: int = Field(ge=0, le=MAX_EXTRA_LATENCY_MS)


def settings_from_env() -> ChaosSettings:
    """Read chaos settings from the environment, failing fast on bad values."""
    return ChaosSettings(
        error_rate=float(os.getenv("CHAOS_ERROR_RATE", "0.02")),
        extra_latency_ms=int(os.getenv("CHAOS_EXTRA_LATENCY_MS", "0")),
    )


chaos = settings_from_env()


def should_fail(error_rate: float, roll: float) -> bool:
    """Decide if this request fails. `roll` is a random number in [0, 1)."""
    return roll < error_rate


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by Docker and load balancers."""
    return {"status": "ok"}


@app.post("/payments")
async def charge(req: PaymentRequest) -> dict[str, str | float]:
    """Simulate a card charge, honouring the current chaos settings."""
    # This span stands in for a call to a real card processor (Stripe etc.).
    # When payments is slow, this is the bar that grows in the trace.
    with tracer.start_as_current_span("card_processor.charge") as span:
        span.set_attribute("app.order_id", req.order_id)
        span.set_attribute("app.payment.amount", req.amount)

        delay_ms = random.uniform(*BASE_LATENCY_MS) + chaos.extra_latency_ms  # noqa: S311
        await asyncio.sleep(delay_ms / 1000)

        if should_fail(chaos.error_rate, random.random()):  # noqa: S311
            # Mark the span as failed so the trace shows it in red.
            span.set_status(Status(StatusCode.ERROR, "card processor error"))
            log.error("card declined by processor order=%s", req.order_id)
            raise HTTPException(status_code=500, detail="card processor error")

    log.info("payment approved order=%s amount=%s", req.order_id, req.amount)
    return {"order_id": req.order_id, "charged": req.amount, "status": "approved"}


@app.get("/chaos")
async def get_chaos() -> ChaosSettings:
    """Return the current chaos settings."""
    return chaos


@app.post("/chaos")
async def set_chaos(settings: ChaosSettings) -> ChaosSettings:
    """Replace the chaos settings at runtime."""
    global chaos  # noqa: PLW0603 (deliberate: one process-wide setting)
    chaos = settings
    log.warning("chaos settings changed: %s", chaos.model_dump())
    return chaos
