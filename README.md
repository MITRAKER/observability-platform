# Observability Platform

[![CI](https://github.com/MITRAKER/observability-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/MITRAKER/observability-platform/actions/workflows/ci.yml)
[![CodeQL](https://github.com/MITRAKER/observability-platform/actions/workflows/codeql.yml/badge.svg)](https://github.com/MITRAKER/observability-platform/actions/workflows/codeql.yml)
[![Release](https://img.shields.io/github/v/release/MITRAKER/observability-platform?sort=semver)](https://github.com/MITRAKER/observability-platform/releases)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Coverage 99%](https://img.shields.io/badge/coverage-99%25-brightgreen.svg)](LEARNING.md#step-5-professional-code-quality-and-ci)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-strict-2a6db2.svg)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

A production-style observability platform for a microservice shop:
OpenTelemetry instrumentation, metrics in Prometheus, traces in Tempo, logs in
Loki, everything correlated in Grafana, with SLOs, burn-rate alerting, chaos
scenarios, and a CI/CD pipeline held to the NASA/JPL "Power of Ten" coding rules.

![Shop overview dashboard](docs/dashboard.png)

## Highlights

- **Three signals, one click apart:** metric exemplar → trace → logs → back to the trace.
- **Service map discovered from real traffic** by Tempo's metrics generator.
- **SLOs with multi-window, multi-burn-rate alerts** (Google SRE Workbook), unit-tested with `promtool`.
- **Chaos scenarios** (`flaky`, `slow`, `outage`) that make the alerts fire for real.
- **Professional engineering:** strict typing, 99% test coverage, security scanning, config validation, a full-stack e2e test in CI, and automated releases.
- **[LEARNING.md](LEARNING.md):** every design decision explained, step by step, with exercises.

## Architecture

```mermaid
flowchart LR
    user([Load generator]) --> gateway
    subgraph shop[Shop services]
        gateway --> orders --> payments
    end
    gateway & orders & payments -- OTLP --> collector[OpenTelemetry Collector]
    collector -- metrics --> prom[(Prometheus)]
    collector -- traces --> tempo[(Tempo)]
    collector -- logs --> loki[(Loki)]
    tempo -- service graph metrics --> prom
    prom -- alerts --> am[Alertmanager] --> sink[Alert sink / pager]
    grafana[Grafana] --> prom & tempo & loki
```

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

## Development

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check . && pytest --cov
```

See [LEARNING.md, step 5](LEARNING.md#step-5-professional-code-quality-and-ci) for the full list of checks.

## Roadmap

- [x] Step 1: Three services, load generator, Docker Compose
- [x] Step 2: OpenTelemetry instrumentation and Collector
- [x] Step 3: Prometheus, Tempo, Loki and Grafana dashboards
- [x] Step 4: SLOs, burn-rate alerts with unit tests, Alertmanager, chaos scenarios, runbooks
- [x] Step 5: CI (lint, strict types, tests with 99% coverage, security scans, config validation, end-to-end smoke test) and NASA/JPL Power of Ten rules
- [x] Step 6: Release automation (images on GHCR), Dependabot, pre-commit, templates, architecture diagram

See [CHANGELOG.md](CHANGELOG.md) for release notes and [CONTRIBUTING.md](CONTRIBUTING.md) to contribute.
