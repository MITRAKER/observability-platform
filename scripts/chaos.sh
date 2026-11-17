#!/usr/bin/env bash
# Switch the payments service between failure scenarios.
#
#   ./scripts/chaos.sh healthy        normal: 2% errors, no extra latency
#   ./scripts/chaos.sh flaky          20% errors        -> CheckoutErrorBudgetFastBurn
#   ./scripts/chaos.sh slow           +300 ms latency   -> CheckoutLatencyBudgetFastBurn
#   ./scripts/chaos.sh outage         100% errors       -> fast burn, every request fails
#   ./scripts/chaos.sh status         show current settings
#
# Alerts need a few minutes to fire (their "for:" clauses). Watch them at
# http://localhost:9090/alerts and in `docker compose logs -f alert-sink`.
set -euo pipefail

PAYMENTS_URL="${PAYMENTS_URL:-http://localhost:8082}"

set_chaos() {
  curl --fail --silent --show-error --max-time 5 \
    -X POST "${PAYMENTS_URL}/chaos" \
    -H 'content-type: application/json' \
    -d "{\"error_rate\": $1, \"extra_latency_ms\": $2}"
  echo
}

case "${1:-}" in
  healthy) set_chaos 0.02 0 ;;
  flaky)   set_chaos 0.20 0 ;;
  slow)    set_chaos 0.02 300 ;;
  outage)  set_chaos 1.0 0 ;;
  status)  curl --fail --silent --show-error --max-time 5 "${PAYMENTS_URL}/chaos"; echo ;;
  *)
    echo "usage: $0 {healthy|flaky|slow|outage|status}" >&2
    exit 2
    ;;
esac
