# Runbooks

Every alert links here. A runbook answers: what does this alert mean, how
bad is it, and what do I check first? Written before the incident, read
during it.

## CheckoutErrorBudgetFastBurn

**Meaning:** more than 14.4% of checkouts are failing with 5xx, sustained
over both the last hour and the last 5 minutes. At this rate the monthly
error budget (1% of requests) is gone in about two days.

**Impact:** customers cannot buy. Page-worthy.

**First checks:**
1. Grafana > Shop overview > "Errors: 5xx %": which service fails *first*?
   Downstream errors (payments) show up as 502s upstream (orders, gateway).
2. "Recent failed or slow traces": open one; the red span is the origin.
3. "Logs for this span" on the red span gives the error message.
4. Demo cause: `./scripts/chaos.sh status`. Fix: `./scripts/chaos.sh healthy`.

## CheckoutErrorBudgetSlowBurn

**Meaning:** more than 6% of checkouts failing over 6 hours and 30 minutes.
A smaller but persistent problem.

**First checks:** same as above; also compare with the last deploy time.

## CheckoutLatencyBudgetFastBurn

**Meaning:** more than 30% of checkouts take longer than 250 ms (SLO: 95%
must be faster).

**First checks:**
1. "Duration: p50 / p95 / p99": which service's latency rose?
2. Click an exemplar dot on the graph to open a slow trace; the widest bar
   is where the time goes (in the demo: `card_processor.charge`).

## ServiceNoTraffic

**Meaning:** a service that had traffic in the last hour has had none for
5 minutes. Either it is down, nothing upstream is calling it, or its
telemetry stopped.

**First checks:** `docker compose ps`, then `docker compose logs <service>`.

## TelemetryPipelineDown

**Meaning:** Prometheus cannot scrape the OpenTelemetry Collector. All other
alerts are blind, so this one suppresses them (see the inhibit rule in
`alertmanager/alertmanager.yml`).

**First checks:** `docker compose logs otel-collector`; is the config valid?
