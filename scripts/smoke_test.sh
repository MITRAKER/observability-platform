#!/usr/bin/env bash
# End-to-end smoke test: start the whole stack, send traffic, and check that
# every signal (metrics, traces, logs) arrived in its backend.
#
# Usage: ./scripts/smoke_test.sh        (expects `docker compose up -d` already done)
# Exits non-zero on the first failed check. Every wait is bounded (JPL rule 2).
set -euo pipefail

GATEWAY="${GATEWAY:-http://localhost:8080}"
PROM="${PROM:-http://localhost:9090}"
TEMPO="${TEMPO:-http://localhost:3200}"
LOKI="${LOKI:-http://localhost:3100}"
GRAFANA="${GRAFANA:-http://localhost:3000}"
MAX_ATTEMPTS=60   # x 5 s = 5 minutes per check at most

# wait_for DESCRIPTION COMMAND...: retry COMMAND until it succeeds or we give up.
wait_for() {
  local what="$1"; shift
  local attempt
  for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
    if "$@" >/dev/null 2>&1; then
      echo "ok   ${what} (attempt ${attempt})"
      return 0
    fi
    sleep 5
  done
  echo "FAIL ${what} after ${MAX_ATTEMPTS} attempts" >&2
  return 1
}

checkout() {
  curl --fail --silent --max-time 5 -X POST "${GATEWAY}/checkout" \
    -H 'content-type: application/json' \
    -d '{"user_id":"smoke","item":"mouse","quantity":1,"unit_price":19.5}'
}

prom_has() {
  curl --fail --silent --max-time 5 -G "${PROM}/api/v1/query" --data-urlencode "query=$1" \
    | grep -q '"result":\[{'
}

tempo_has_traces() {
  curl --fail --silent --max-time 5 "${TEMPO}/api/search?tags=service.name%3Dgateway&limit=1" \
    | grep -q '"traceID"'
}

loki_has_logs() {
  curl --fail --silent --max-time 5 -G "${LOKI}/loki/api/v1/query_range" \
    --data-urlencode 'query={service_name="orders"}' --data-urlencode 'limit=1' \
    | grep -q '"values":\[\['
}

grafana_has_dashboards() {
  curl --fail --silent --max-time 5 "${GRAFANA}/api/search?query=Shop" | grep -q 'shop-overview'
}

wait_for "gateway answers /health" curl --fail --silent --max-time 5 "${GATEWAY}/health"
wait_for "a checkout succeeds" checkout
wait_for "Prometheus has shop_orders_total" prom_has 'shop_orders_total'
wait_for "Prometheus has HTTP metrics" prom_has 'http_server_duration_milliseconds_count{service_name="payments"}'
wait_for "Prometheus has the service graph" prom_has 'traces_service_graph_request_total'
wait_for "Prometheus loaded SLO rules" prom_has 'slo:checkout_errors:ratio_rate5m'
wait_for "Tempo has gateway traces" tempo_has_traces
wait_for "Loki has orders logs" loki_has_logs
wait_for "Grafana provisioned dashboards" grafana_has_dashboards
echo "smoke test passed"
