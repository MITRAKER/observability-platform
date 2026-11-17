# Learning notes

This file grows with each step of the project. Each section explains what was
built, why it was built that way, and the ideas you need to build it yourself.

## Contents

1. [Step 1: Three services and Docker Compose](#step-1-three-services-and-docker-compose)
2. [Step 2: OpenTelemetry and the Collector](#step-2-opentelemetry-and-the-collector)
3. [Step 3: Prometheus, Tempo, Loki and Grafana](#step-3-prometheus-tempo-loki-and-grafana)

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

---

## Step 3: Prometheus, Tempo, Loki and Grafana

### What we built

Each signal now lands in a real backend, and Grafana shows all three in one
dashboard where you can click from one to another.

```
                                ┌─ metrics ─> :8889 <── scraped by ── Prometheus ─┐
 services ─ OTLP ─> Collector ──┼─ traces ──> Tempo ── service-graph metrics ──>  │
                                └─ logs ────> Loki                                │
                                                                                  v
                                      Grafana  <── queries Prometheus, Tempo, Loki
```

![Shop overview dashboard](docs/dashboard.png)

| File | What it does |
|---|---|
| `otel-collector/config.yaml` | Three exporters now: `prometheus`, `otlp/tempo`, `otlphttp/loki`. |
| `prometheus/prometheus.yml` | Scrapes the Collector every 10 s. |
| `tempo/tempo.yaml` | Stores traces and generates service-graph and span metrics. |
| `loki/loki.yaml` | Stores logs, keeps `trace_id` as structured metadata. |
| `grafana/provisioning/datasources/datasources.yaml` | The three data sources plus the links between them. |
| `grafana/provisioning/dashboards/dashboards.yaml` | Tells Grafana to load dashboards from a folder. |
| `grafana/dashboards/shop-overview.json` | The "Shop overview" dashboard. |

Open http://localhost:3000 and go to Dashboards > Shop > Shop overview.

### Why each tool

**Prometheus (metrics).** The industry default for metrics. It stores numbers
as *time series* (a metric name + labels -> a value every 10 s) and has a
query language, PromQL. It **pulls**: every 10 s it calls an HTTP endpoint
and reads the current values. The Collector's `prometheus` exporter provides
that endpoint.

**Tempo (traces).** Grafana's trace store. It only indexes the trace ID and a
few fields, and keeps everything else in cheap object storage, so it can
store 100% of traces instead of a sample. You search with **TraceQL**, e.g.
`{ status = error || duration > 300ms }`.

**Loki (logs).** "Prometheus, but for logs." It indexes only labels like
`service_name`, not the full text, which makes it much cheaper than
Elasticsearch. You query with **LogQL**: pick streams with labels, then
filter: `{service_name="orders"} |= "payment failed"`.

**Grafana (UI).** Talks to all three. The value is not just pretty graphs: it
is **correlation**, jumping between signals with one click.

### Key concepts

1. **Push vs pull.** Services *push* OTLP to the Collector. Prometheus *pulls*
   from the Collector. Tempo *pushes* its generated metrics into Prometheus
   (remote write). Knowing which way data flows tells you where to look when
   data is missing.

2. **How OTel names become Prometheus names.** The exporter converts dots to
   underscores and adds units and suffixes: `shop.orders` (a counter) becomes
   `shop_orders_total`; `http.server.duration` in ms becomes
   `http_server_duration_milliseconds_bucket/_sum/_count`. Resource
   attributes become labels like `service_name`.

3. **The RED method.** For every service that handles requests, watch:
   **R**ate (requests/s), **E**rrors (% failing), **D**uration (latency
   percentiles). The middle row of the dashboard is exactly that. (For
   resources like CPU or disks, the matching method is USE: Utilization,
   Saturation, Errors.)

4. **PromQL in four patterns.** Every query in the dashboard is one of these:
   ```promql
   # rate: per-second increase of a counter over the last minute
   sum by (service_name) (rate(http_server_duration_milliseconds_count[1m]))

   # error ratio: failing rate divided by total rate
   sum(rate(..._count{http_status_code=~"5.."}[1m])) / sum(rate(..._count[1m]))

   # percentile from a histogram: always keep "le" in the "by" clause
   histogram_quantile(0.95, sum by (le, service_name) (rate(..._bucket[1m])))

   # per-minute value: rate is per second, so multiply by 60
   sum(rate(shop_order_value_USD_sum[5m])) * 60
   ```
   Never graph a raw counter: it only goes up and resets when a service
   restarts. `rate()` handles both.

5. **Why percentiles, not averages.** If 99 requests take 50 ms and one takes
   5 s, the average is 100 ms and looks fine, but 1 in 100 users waits 5 s.
   p95/p99 show the experience of your unluckiest users. Note: percentiles
   from histograms are *estimates* interpolated inside buckets, which is why
   "Order value p95" can show $600 even though the largest order is $567.

6. **Exemplars.** The dots on the latency graph. Each one is a real
   measurement with the `trace_id` of the request it came from. Click one and
   Grafana opens that trace. This is the fastest route from "latency is high"
   to "here is a slow request".

7. **Service graph from traces.** Tempo's metrics generator looks at
   parent/child spans across services and produces
   `traces_service_graph_request_total{client="orders",server="payments"}`.
   Grafana draws the service map from those metrics. No one had to draw the
   architecture by hand: it is discovered from real traffic.

8. **Correlation links (configured in `datasources.yaml`).**
   - Metric -> trace: `exemplarTraceIdDestinations`
   - Trace -> logs: `tracesToLogsV2` (a "Logs for this span" button)
   - Log -> trace: `derivedFields` on Loki (a "View trace" button using the
     `trace_id` stored with each log line)

9. **Labels vs structured metadata in Loki.** Labels define *streams* and are
   indexed, so they must be low-cardinality (`service_name`, maybe `level`).
   High-cardinality values like `trace_id` are stored as *structured metadata*:
   searchable, but not indexed. Same cardinality rule as Prometheus.

10. **Provisioning (config as code).** Data sources and dashboards live in
    files in Git. Delete every container, run `docker compose up` again, and
    Grafana comes back exactly the same. No clicking, nothing lost, and changes
    go through code review.

### Try it yourself

```bash
docker compose up --build
# Grafana:    http://localhost:3000   (Dashboards > Shop > Shop overview)
# Prometheus: http://localhost:9090   (try the PromQL queries above)

# Cause an incident and watch the dashboard react within ~30 s
curl -X POST localhost:8082/chaos -H 'content-type: application/json' \
     -d '{"error_rate":0.15,"extra_latency_ms":250}'
```

Then practise the investigation flow you would use on call:
1. Overview: success rate drops, p95 latency rises.
2. RED row: errors are in payments first; gateway and orders just pass them on.
3. Click an exemplar dot on the latency graph -> a slow trace opens. The long
   bar is `card_processor.charge`.
4. In the trace, click "Logs for this span" -> `card declined by processor`.
5. In Explore > Loki, run
   `{service_name="payments"} | severity_text="ERROR"` and click "View trace"
   on a line to go back.

**Exercises:**
- Add a panel "Requests by endpoint" using `sum by (http_target) (rate(http_server_duration_milliseconds_count[1m]))`.
- In Explore > Tempo, write a TraceQL query for checkouts by one user:
  `{ span.app.user_id = "user-7" }`.
- In Explore > Loki, count errors per service:
  `sum by (service_name) (count_over_time({service_namespace="shop"} | severity_number >= 17 [1m]))`.

### What is missing (and why step 4 exists)

Nobody stares at dashboards all day. Step 4 defines what "good enough" means
(SLOs), and adds alerts that fire when the shop is burning through its error
budget too fast, plus scripted chaos scenarios to test them.
