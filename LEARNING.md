# Learning notes

This file grows with each step of the project. Each section explains what was
built, why it was built that way, and the ideas you need to build it yourself.

---

## Step 1: Three services and Docker Compose

### What we built

A tiny online shop split into three small programs ("microservices"):

```
 you / loadgen
      |
      v
  gateway  :8080      checks the request, forwards it
      |
      v
   orders             creates the order, asks payments to charge
      |
      v
  payments  :8082     pretends to charge a card (and can be told to fail)
```

Plus a **load generator** that plays the role of users, and a
`docker-compose.yml` that starts all four with one command.

| File | What it does |
|---|---|
| `services/gateway/main.py` | `POST /checkout`. Validates input, calls orders. |
| `services/orders/main.py` | `POST /orders`. Computes the amount, calls payments, stores the order. |
| `services/payments/main.py` | `POST /payments`. Sleeps 20-120 ms, fails 2% of the time. `POST /chaos` changes that. |
| `services/Dockerfile` | One Dockerfile for all three services. |
| `loadgen/loadgen.py` | Sends N checkout requests per second, forever. |
| `docker-compose.yml` | Starts everything on a private network. |

### Why it is designed this way

**Why three services and not one?** Observability matters most when one user
request crosses several programs. If checkout is slow, you need to know
*which* service is slow. With a single program you would never need traces.
The chain gateway -> orders -> payments is the smallest setup that makes
distributed tracing worth showing.

**Why a "chaos" switch?** A healthy system gives flat, boring graphs. To prove
your dashboards and alerts work, you need to break things on purpose. Payments
has an error rate and an extra delay you can change while it runs. This idea
is called *chaos engineering* (Netflix made it famous with Chaos Monkey).

**Why a load generator?** Metrics only exist when traffic exists. Real systems
have users; a demo needs fake ones.

**Why FastAPI?** It is short to read, async (handles many requests at once
without threads), validates input from type hints (`quantity: int = Field(gt=0)`
gives you a 422 error for free), and has first-class OpenTelemetry support,
which we use in step 2.

### Key concepts

1. **Microservices talk over HTTP.** Each service is a web server. Orders
   calls payments the same way your browser calls a website: `POST
   http://payments:8000/payments` with a JSON body.

2. **Docker image vs container.** The `Dockerfile` is a recipe. Building it
   gives an *image* (a frozen snapshot of Python + your code). Running an image
   gives a *container* (a live process). We build one image per service.

3. **Layer caching.** In the Dockerfile we copy `requirements.txt` and run
   `pip install` *before* copying the code. Docker caches each step. When you
   only change code, it reuses the cached install and rebuilds in seconds.

4. **Build arguments.** `ARG SERVICE` lets one Dockerfile build three images:
   compose passes `SERVICE: gateway`, `SERVICE: orders`, and so on.

5. **Docker Compose networking.** Compose puts all services on one private
   network, where each service's *name* is its hostname. That is why orders
   can reach `http://payments:8000` without knowing any IP address. Only
   ports listed under `ports:` are reachable from your own machine.

6. **Configuration through environment variables.** URLs and chaos settings
   come from `os.getenv(...)`. The same image can then run on your laptop, in
   tests, or in production with different settings. This is one of the
   "Twelve-Factor App" rules.

7. **Error propagation.** If payments fails, orders returns `502 Bad
   Gateway` ("someone I depend on failed"), and if a service cannot be reached
   at all you get `503 Service Unavailable`. Choosing the right status code
   matters: in step 3 we will count 5xx responses to measure the error rate.

8. **Timeouts.** Every `httpx.AsyncClient` has `timeout=5.0`. Without a
   timeout, one stuck service can make every service that calls it hang too.

### Try it yourself

```bash
docker compose up --build          # start everything
curl -X POST localhost:8080/checkout -H 'content-type: application/json' \
     -d '{"user_id":"u1","item":"mouse","quantity":2,"unit_price":19.5}'

# Break payments: every request fails
curl -X POST localhost:8082/chaos -H 'content-type: application/json' \
     -d '{"error_rate":1.0,"extra_latency_ms":0}'
# Now the checkout call above returns 502. Set error_rate back to 0.02.

docker compose logs -f loadgen     # watch the fake users
```

### What is missing (and why step 2 exists)

Right now, if checkout gets slow, all you can do is read logs from four
containers and guess. There are no numbers over time (metrics), no way to
follow one request across services (traces), and logs are not connected to
anything. Step 2 adds OpenTelemetry to fix exactly that.
