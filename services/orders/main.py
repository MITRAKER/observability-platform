"""Orders: creates an order, asks payments to charge it, and stores the result.

Orders are kept in memory to keep the demo small. A real system would use a
database, and a database call would just be one more span in the trace.

Besides the automatic HTTP spans, this service shows the three kinds of
custom telemetry you will write in real jobs:
  * a manual span      (pricing the order)
  * custom metrics     (orders counter, order value histogram)
  * logs               (that carry the trace id, so you can jump to the trace)
"""
import logging
import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from opentelemetry import metrics, trace
from pydantic import BaseModel

PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:8000")

log = logging.getLogger("orders")
tracer = trace.get_tracer("orders")
meter = metrics.get_meter("orders")

# A counter only goes up. We split it by status with an attribute,
# so one metric answers "how many orders were paid vs failed".
orders_counter = meter.create_counter(
    "shop.orders",
    unit="{order}",
    description="Orders created, by final status",
)
# A histogram records a distribution: we can ask for the average order
# value, or the 95th percentile, later in Prometheus.
order_value = meter.create_histogram(
    "shop.order.value",
    unit="USD",
    description="Value of paid orders",
)

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

    # A manual span: shows up as its own bar inside the request's trace.
    with tracer.start_as_current_span("price_order") as span:
        amount = round(req.quantity * req.unit_price, 2)
        span.set_attribute("app.order_id", order_id)
        span.set_attribute("app.order.amount", amount)

    try:
        resp = await client.post(
            f"{PAYMENTS_URL}/payments",
            json={"order_id": order_id, "user_id": req.user_id, "amount": amount},
        )
    except httpx.RequestError as exc:
        orders_counter.add(1, {"status": "payments_unreachable", "item": req.item})
        log.error("payments unreachable for order=%s: %s", order_id, exc)
        raise HTTPException(status_code=503, detail=f"payments unavailable: {exc}")

    if resp.status_code >= 400:
        ORDERS[order_id] = {"status": "payment_failed", **req.model_dump()}
        orders_counter.add(1, {"status": "payment_failed", "item": req.item})
        log.warning("payment failed for order=%s amount=%s", order_id, amount)
        raise HTTPException(status_code=502, detail="payment failed")

    order = {"order_id": order_id, "status": "paid", "amount": amount, **req.model_dump()}
    ORDERS[order_id] = order
    orders_counter.add(1, {"status": "paid", "item": req.item})
    order_value.record(amount, {"item": req.item})
    log.info("order paid order=%s amount=%s", order_id, amount)
    return order


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    if order_id not in ORDERS:
        raise HTTPException(status_code=404, detail="order not found")
    return ORDERS[order_id]
