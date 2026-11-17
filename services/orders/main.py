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
from collections import OrderedDict
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://payments:8000")
REQUEST_TIMEOUT_S = 5.0
MAX_STORED_ORDERS = 10_000  # JPL rule 3: memory use has a fixed upper bound

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


class BoundedStore:
    """An in-memory key/value store that never holds more than `capacity` items.

    When full, the oldest entry is dropped. An unbounded dict would grow
    forever under constant load and eventually crash the service.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def put(self, key: str, value: dict[str, Any]) -> None:
        """Store `value` under `key`, evicting the oldest entry if full."""
        self._items[key] = value
        self._items.move_to_end(key)
        if len(self._items) > self._capacity:
            self._items.popitem(last=False)

    def get(self, key: str) -> dict[str, Any] | None:
        """Return the stored value, or None if absent."""
        return self._items.get(key)

    def __len__(self) -> int:
        return len(self._items)


app = FastAPI(title="orders")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S)
ORDERS = BoundedStore(MAX_STORED_ORDERS)


class OrderRequest(BaseModel):
    """Body of POST /orders, as sent by the gateway."""

    user_id: str = Field(min_length=1, max_length=64)
    item: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0, le=10)
    unit_price: float = Field(gt=0, le=10_000)


def price_order(order_id: str, req: OrderRequest) -> float:
    """Compute the order total inside its own span."""
    # A manual span: shows up as its own bar inside the request's trace.
    with tracer.start_as_current_span("price_order") as span:
        amount = round(req.quantity * req.unit_price, 2)
        if amount <= 0:  # invariant: validated input can never price to zero
            raise ValueError(f"non-positive amount {amount} for order {order_id}")
        span.set_attribute("app.order_id", order_id)
        span.set_attribute("app.order.amount", amount)
    return amount


async def charge(order_id: str, user_id: str, amount: float) -> httpx.Response:
    """Ask the payments service to charge the order. Raises 503 if unreachable."""
    try:
        return await client.post(
            f"{PAYMENTS_URL}/payments",
            json={"order_id": order_id, "user_id": user_id, "amount": amount},
        )
    except httpx.RequestError as exc:
        log.error("payments unreachable for order=%s: %s", order_id, exc)
        raise HTTPException(status_code=503, detail="payments unavailable") from exc


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by Docker and load balancers."""
    return {"status": "ok"}


@app.post("/orders")
async def create_order(req: OrderRequest) -> dict[str, Any]:
    """Create an order, charge it, and record the outcome in metrics and logs."""
    order_id = str(uuid.uuid4())
    amount = price_order(order_id, req)

    try:
        resp = await charge(order_id, req.user_id, amount)
    except HTTPException:
        orders_counter.add(1, {"status": "payments_unreachable", "item": req.item})
        raise

    if resp.is_error:
        ORDERS.put(order_id, {"status": "payment_failed", **req.model_dump()})
        orders_counter.add(1, {"status": "payment_failed", "item": req.item})
        log.warning("payment failed for order=%s amount=%s", order_id, amount)
        raise HTTPException(status_code=502, detail="payment failed")

    order = {"order_id": order_id, "status": "paid", "amount": amount, **req.model_dump()}
    ORDERS.put(order_id, order)
    orders_counter.add(1, {"status": "paid", "item": req.item})
    order_value.record(amount, {"item": req.item})
    log.info("order paid order=%s amount=%s", order_id, amount)
    return order


@app.get("/orders/{order_id}")
async def get_order(order_id: str) -> dict[str, Any]:
    """Return a stored order, or 404."""
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order
