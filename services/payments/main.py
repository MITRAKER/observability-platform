"""Payments: pretends to charge a card.

Two environment variables turn on "chaos" so the dashboards and alerts we add
later have something to show:
  CHAOS_ERROR_RATE  share of requests that fail, from 0.0 to 1.0 (default 0.02)
  CHAOS_EXTRA_LATENCY_MS  extra delay added to every request (default 0)
You can also change them while the service runs with POST /chaos.
"""
import asyncio
import os
import random

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="payments")

chaos = {
    "error_rate": float(os.getenv("CHAOS_ERROR_RATE", "0.02")),
    "extra_latency_ms": int(os.getenv("CHAOS_EXTRA_LATENCY_MS", "0")),
}


class PaymentRequest(BaseModel):
    order_id: str
    user_id: str
    amount: float


class ChaosSettings(BaseModel):
    error_rate: float = Field(ge=0.0, le=1.0)
    extra_latency_ms: int = Field(ge=0, le=10_000)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/payments")
async def charge(req: PaymentRequest):
    # Normal work takes 20-120 ms, plus whatever chaos adds.
    delay_ms = random.uniform(20, 120) + chaos["extra_latency_ms"]
    await asyncio.sleep(delay_ms / 1000)

    if random.random() < chaos["error_rate"]:
        raise HTTPException(status_code=500, detail="card processor error")

    return {"order_id": req.order_id, "charged": req.amount, "status": "approved"}


@app.get("/chaos")
async def get_chaos():
    return chaos


@app.post("/chaos")
async def set_chaos(settings: ChaosSettings):
    chaos.update(settings.model_dump())
    return chaos
