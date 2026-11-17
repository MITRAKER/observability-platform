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

import httpx
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from pydantic import BaseModel, Field

ORDERS_URL = os.getenv("ORDERS_URL", "http://orders:8000")

log = logging.getLogger("gateway")
app = FastAPI(title="gateway")
client = httpx.AsyncClient(timeout=5.0)


class CheckoutRequest(BaseModel):
    user_id: str
    item: str
    quantity: int = Field(gt=0, le=10)
    unit_price: float = Field(gt=0)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/checkout")
async def checkout(req: CheckoutRequest):
    # The FastAPI instrumentation already opened a span for this request.
    # We attach business data to it so we can search traces by user later.
    span = trace.get_current_span()
    span.set_attribute("app.user_id", req.user_id)
    span.set_attribute("app.item", req.item)

    try:
        resp = await client.post(f"{ORDERS_URL}/orders", json=req.model_dump())
    except httpx.RequestError as exc:
        log.error("orders service unreachable: %s", exc)
        raise HTTPException(status_code=503, detail=f"orders unavailable: {exc}")

    if resp.status_code >= 400:
        log.warning("checkout failed for user=%s status=%s", req.user_id, resp.status_code)
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))

    log.info("checkout ok for user=%s item=%s", req.user_id, req.item)
    return resp.json()
