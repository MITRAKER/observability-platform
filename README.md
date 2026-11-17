# Observability Platform

A hands-on observability project: a small microservice shop instrumented with
OpenTelemetry, with metrics in Prometheus, traces in Tempo, logs in Loki, and
everything visualised in Grafana.

> Work in progress. See [LEARNING.md](LEARNING.md) for step-by-step notes on
> how and why each piece was built.

## Run it

```bash
docker compose up --build
```

- Shop gateway: http://localhost:8080 (API docs at http://localhost:8080/docs)
- Payments (for the chaos switch): http://localhost:8082/docs

## Roadmap

- [x] Step 1: Three services, load generator, Docker Compose
- [ ] Step 2: OpenTelemetry instrumentation and Collector
- [ ] Step 3: Prometheus, Tempo, Loki and Grafana dashboards
- [ ] Step 4: SLOs, alert rules, chaos scenarios
- [ ] Step 5: Architecture diagram, screenshots, CI
