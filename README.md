# Observability Platform

A hands-on observability project: a small microservice shop instrumented with
OpenTelemetry, with metrics in Prometheus, traces in Tempo, logs in Loki, and
everything correlated in Grafana.

![Shop overview dashboard](docs/dashboard.png)

> Work in progress. See [LEARNING.md](LEARNING.md) for step-by-step notes on
> how and why each piece was built.

## Run it

```bash
docker compose up --build
```

| What | Where |
|---|---|
| Grafana (dashboard: Shop > Shop overview) | http://localhost:3000 |
| Prometheus (alerts at /alerts) | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Shop gateway API | http://localhost:8080/docs |
| Payments chaos switch | http://localhost:8082/docs |

Cause an incident and watch the SLO alerts fire:

```bash
./scripts/chaos.sh flaky          # or: slow, outage, healthy
docker compose logs -f alert-sink # the "pager"
```

![SLO dashboard during an incident](docs/slo-dashboard.png)

## Roadmap

- [x] Step 1: Three services, load generator, Docker Compose
- [x] Step 2: OpenTelemetry instrumentation and Collector
- [x] Step 3: Prometheus, Tempo, Loki and Grafana dashboards
- [x] Step 4: SLOs, burn-rate alerts with unit tests, Alertmanager, chaos scenarios, runbooks
- [ ] Step 5: Architecture diagram, CI
