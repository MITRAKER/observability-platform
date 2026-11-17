"""Sends a steady stream of checkout requests to the gateway.

Without traffic, every dashboard is empty. This script is the "users".
Usage: python loadgen.py [requests_per_second]
"""
import asyncio
import os
import random
import sys

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")
RPS = float(sys.argv[1]) if len(sys.argv) > 1 else float(os.getenv("RPS", "5"))
ITEMS = [("keyboard", 49.0), ("mouse", 19.5), ("monitor", 189.0), ("cable", 7.25)]


async def one_request(client: httpx.AsyncClient):
    item, price = random.choice(ITEMS)
    body = {
        "user_id": f"user-{random.randint(1, 50)}",
        "item": item,
        "quantity": random.randint(1, 3),
        "unit_price": price,
    }
    try:
        resp = await client.post(f"{GATEWAY_URL}/checkout", json=body)
        print(resp.status_code, item, flush=True)
    except httpx.RequestError as exc:
        print("ERR", exc, flush=True)


async def main():
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            asyncio.create_task(one_request(client))
            await asyncio.sleep(1 / RPS)


if __name__ == "__main__":
    asyncio.run(main())
