# Learning notes

This file grows with each step of the project. Each section explains what was
built, why it was built that way, and the ideas you need to build it yourself.

## Contents

1. [Step 1: Three services and Docker Compose](#step-1-three-services-and-docker-compose)
2. [Step 2: OpenTelemetry and the Collector](#step-2-opentelemetry-and-the-collector)

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

---

## Step 2: OpenTelemetry and the Collector

### What we built

Every service now produces the **three signals** of observability and sends
them to an **OpenTelemetry Collector**:

```
 gateway ─┐
 orders  ─┼── OTLP (traces + metrics + logs) ──>  otel-collector  ──> (step 3: Prometheus, Tempo, Loki)
 payments ┘                                       today: prints to its own log
```

| File | Change |
|---|---|
| `services/requirements.txt` | Adds the OpenTelemetry SDK, OTLP exporter and auto-instrumentation packages. |
| `services/Dockerfile` | Starts the app through `opentelemetry-instrument`. |
| `services/*/main.py` | Adds span attributes, one manual span per service, two custom metrics, and log lines. |
| `otel-collector/config.yaml` | The Collector pipeline: receive, process, export. |
| `docker-compose.yml` | Adds the Collector and shared `OTEL_*` settings. |

### The three signals

| Signal | Question it answers | Example here |
|---|---|---|
| **Metrics** | "How much / how often / how fast, over time?" Cheap numbers, aggregated. | `shop.orders` counter split by `status`, request duration histograms. |
| **Traces** | "What happened to *this one* request, step by step, across services?" | One checkout = one trace with spans in gateway, orders and payments. |
| **Logs** | "What exactly did the code say at that moment?" | `payment failed for order=... amount=...` |

The power comes from **connecting** them: a metric shows errors went up, you
click into a trace of a failed request, and from the trace you jump to the
exact log lines (they share the same `trace_id`).

### Why it is designed this way

**Why OpenTelemetry instead of a Prometheus client library?** OpenTelemetry
(OTel) is the vendor-neutral standard. You instrument the code once, and the
data can go to Prometheus, Grafana, Datadog, New Relic, Honeycomb, and so on,
by changing Collector config, not code. That is why every job ad for
observability mentions it.

**Why auto-instrumentation?** `opentelemetry-instrument` patches FastAPI and
httpx at startup. Without writing a line of tracing code we get a span for
every incoming request, a span for every outgoing call, and standard HTTP
metrics (`http.server.duration` etc.). We only add custom code where business
meaning is needed (which user? how much money?).

**Why a Collector in the middle, instead of apps sending straight to
backends?**
- Apps only know one address (`otel-collector:4318`). Swapping a backend
  never touches app code.
- Batching, retries and memory limits live in one place.
- You can add, drop, rename or redact data centrally (for example, remove
  credit-card numbers before they leave your network).

**Why OTLP over HTTP (port 4318) and not gRPC (4317)?** Both work. The HTTP
exporter has fewer dependencies (no `grpcio`, which is large to install), so
images build faster. The Collector listens on both.

### Key concepts

1. **Trace, span, context propagation.** A *trace* is the whole journey of
   one request. A *span* is one step in it, with a start time, a duration, a
   name, attributes and a status. When gateway calls orders, the httpx
   instrumentation adds a `traceparent` HTTP header holding the trace id.
   Orders reads that header and creates its spans *inside the same trace*.
   This is **context propagation** and it is the whole trick behind
   distributed tracing. (The header format is the W3C Trace Context standard.)

2. **Span attributes.** Key/value pairs on a span, like
   `app.user_id=user-7`. In step 3 you will search Tempo for "all traces where
   `app.user_id=user-7`".

3. **Manual spans.** `with tracer.start_as_current_span("price_order"):`
   creates a child span for a block of code you care about. In payments,
   `card_processor.charge` is the span that grows when we turn on chaos
   latency, which makes the slow part obvious in a trace.

4. **Span status.** `span.set_status(Status(StatusCode.ERROR, ...))` marks a
   span as failed so trace viewers show it in red.

5. **Metric instruments.**
   - *Counter*: only goes up (`shop.orders`). You later compute a *rate*
     ("orders per second").
   - *Histogram*: records a distribution (`shop.order.value`). You later ask
     for averages or percentiles (p50, p95, p99).
   - *Attributes* (labels) split one metric into series, like
     `status=paid` vs `status=payment_failed`.
   - **Cardinality warning:** never use unbounded values (user ids, order
     ids) as metric attributes. Each unique value creates a new time series
     and can blow up Prometheus. Put those on spans instead. That is why
     `user_id` is a span attribute but `item` (4 possible values) is a metric
     attribute.

6. **Resource attributes.** Data describing *who* sent the telemetry:
   `service.name`, `service.version`, `deployment.environment`. Set through
   `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES`, and by the Collector's
   `resource` processor.

7. **Log correlation.** `OTEL_PYTHON_LOG_CORRELATION=true` stamps every log
   record with the current `trace_id` and `span_id`. Run the services and you
   will see lines like
   `[trace_id=8190...518a span_id=2c85...3572 resource.service.name=orders] - order paid ...`

8. **The Collector pipeline.** Receivers (`otlp`) -> processors
   (`memory_limiter`, `resource`, `batch`) -> exporters (`debug` for now). One
   pipeline per signal. Order matters: `memory_limiter` goes first so it can
   refuse data before anything else spends memory on it.

### Try it yourself

```bash
docker compose up --build
docker compose logs -f otel-collector
```

You will see lines like `Traces {"resource spans": 3, "spans": 9}` every
few seconds. To see full detail, change `verbosity: basic` to
`verbosity: detailed` in `otel-collector/config.yaml` and restart the
Collector. Then:

```bash
# Make payments slow and broken
curl -X POST localhost:8082/chaos -H 'content-type: application/json' \
     -d '{"error_rate":0.5,"extra_latency_ms":400}'
```

In the detailed output, look for spans named `card_processor.charge` with
`Status code: Error`, and log records with `Body: card declined by processor`
whose `Trace ID` matches.

**Exercise:** add a manual span in the gateway around input validation, and a
counter `shop.checkouts` with an attribute `result` (`ok` / `failed`).

### What is missing (and why step 3 exists)

Reading telemetry in a terminal log does not scale. Step 3 sends metrics to
**Prometheus**, traces to **Tempo** and logs to **Loki**, and puts all three
in **Grafana** dashboards where you can click from one signal to another.
