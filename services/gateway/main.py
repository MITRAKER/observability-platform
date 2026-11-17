"""Gateway: the public front door of the demo shop.

A client calls POST /checkout. The gateway checks the request and forwards it
to the orders service. It never talks to payments directly; that keeps the
call chain gateway -> orders -> payments, which is what makes distributed
tracing interesting later on.
"""
import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ORDERS_URL = os.getenv("ORDERS_URL", "http://orders:8000")

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
    try:
        resp = await client.post(f"{ORDERS_URL}/orders", json=req.model_dump())
    except httpx.RequestError as exc:
        # The orders service is down or too slow.
        raise HTTPException(status_code=503, detail=f"orders unavailable: {exc}")

    if resp.status_code >= 400:
        # Pass the downstream error through so the client sees what happened.
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail"))
    return resp.json()
