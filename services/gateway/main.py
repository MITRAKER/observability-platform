"""Gateway: the public front door of the demo shop.

A client calls POST /checkout. The gateway checks the request and forwards it
to the orders service. It never talks to payments directly; that keeps the
call chain gateway -> orders -> payments, which is what makes distributed
tracing interesting.

Tracing of incoming requests (FastAPI) and outgoing calls (httpx) is done
automatically by `opentelemetry-instrument`. This file only adds business
details on top: a span attribute and a log line.
"""

import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from pydantic import BaseModel, Field

ORDERS_URL = os.getenv("ORDERS_URL", "http://orders:8000")
REQUEST_TIMEOUT_S = 5.0

log = logging.getLogger("gateway")
app = FastAPI(title="gateway")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S)


class CheckoutRequest(BaseModel):
    """Body of POST /checkout. Pydantic rejects bad input with a 422."""

    user_id: str = Field(min_length=1, max_length=64)
    item: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0, le=10)
    unit_price: float = Field(gt=0, le=10_000)


def error_detail(resp: httpx.Response) -> str:
    """Return the downstream error message, even if the body is not JSON."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200] or "downstream error"
    detail = body.get("detail") if isinstance(body, dict) else None
    return detail if isinstance(detail, str) else "downstream error"


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by Docker and load balancers."""
    return {"status": "ok"}


@app.post("/checkout")
async def checkout(req: CheckoutRequest) -> dict[str, Any]:
    """Validate a checkout and forward it to the orders service."""
    # The FastAPI instrumentation already opened a span for this request.
    # We attach business data to it so we can search traces by user later.
    span = trace.get_current_span()
    span.set_attribute("app.user_id", req.user_id)
    span.set_attribute("app.item", req.item)

    try:
        resp = await client.post(f"{ORDERS_URL}/orders", json=req.model_dump())
    except httpx.RequestError as exc:
        log.error("orders service unreachable: %s", exc)
        raise HTTPException(status_code=503, detail="orders unavailable") from exc

    if resp.is_error:
        log.warning("checkout failed for user=%s status=%s", req.user_id, resp.status_code)
        raise HTTPException(status_code=resp.status_code, detail=error_detail(resp))

    order: dict[str, Any] = resp.json()
    log.info("checkout ok for user=%s item=%s", req.user_id, req.item)
    return order
