"""Orders: creates an order, asks payments to charge it, and stores the result.

Orders are kept in memory to keep the demo small. A real system would use a
database, and a database call would just be one more span in the trace.
"""
import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:8000")

app = FastAPI(title="orders")
client = httpx.AsyncClient(timeout=5.0)
ORDERS: dict[str, dict] = {}


class OrderRequest(BaseModel):
    user_id: str
    item: str
    quantity: int
    unit_price: float


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/orders")
async def create_order(req: OrderRequest):
    order_id = str(uuid.uuid4())
    amount = round(req.quantity * req.unit_price, 2)

    try:
        resp = await client.post(
            f"{PAYMENTS_URL}/payments",
            json={"order_id": order_id, "user_id": req.user_id, "amount": amount},
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"payments unavailable: {exc}")

    if resp.status_code >= 400:
        ORDERS[order_id] = {"status": "payment_failed", **req.model_dump()}
        raise HTTPException(status_code=502, detail="payment failed")

    order = {"order_id": order_id, "status": "paid", "amount": amount, **req.model_dump()}
    ORDERS[order_id] = order
    return order


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="order not found")
    return ORDERS[order_id]
