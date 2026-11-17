import json, sys
P = {"type": "prometheus", "uid": "prometheus"}
L = {"type": "loki", "uid": "loki"}
T = {"type": "tempo", "uid": "tempo"}
SEL = 'service_name=~"$service"'
panels = []
pid = 0
def add(p, x, y, w, h):
    global pid
    pid += 1
    p["id"] = pid
    p["gridPos"] = {"x": x, "y": y, "w": w, "h": h}
    panels.append(p)
def row(title, y):
    add({"type": "row", "title": title, "collapsed": False, "panels": []}, 0, y, 24, 1)
def ts(title, desc, targets, unit, x, y, w=8, h=8, extra=None):
    p = {"type": "timeseries", "title": title, "description": desc, "datasource": P,
         "targets": [dict(t, datasource=P, refId=chr(65+i)) for i, t in enumerate(targets)],
         "fieldConfig": {"defaults": {"unit": unit, "custom": {"fillOpacity": 10, "showPoints": "never"}}, "overrides": []},
         "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}}
    if extra: p["fieldConfig"]["defaults"].update(extra)
    add(p, x, y, w, h)
def stat(title, desc, expr, unit, x, y, thresholds, w=6, h=4):
    add({"type": "stat", "title": title, "description": desc, "datasource": P,
         "targets": [{"expr": expr, "refId": "A", "datasource": P, "instant": False}],
         "fieldConfig": {"defaults": {"unit": unit, "decimals": 2, "color": {"mode": "thresholds"},
                          "thresholds": {"mode": "absolute", "steps": thresholds}}, "overrides": []},
         "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background", "graphMode": "area"}}, x, y, w, h)

G, R, Y = "green", "red", "orange"
row("Overview", 0)
stat("Checkout success rate", "Share of /checkout calls at the gateway that did not return 5xx (last 5 min).",
     '100 * (1 - (sum(rate(http_server_duration_milliseconds_count{service_name="gateway",http_status_code=~"5.."}[5m])) or vector(0)) / sum(rate(http_server_duration_milliseconds_count{service_name="gateway"}[5m])))',
     "percent", 0, 1, [{"color": R, "value": None}, {"color": Y, "value": 95}, {"color": G, "value": 99}])
stat("Checkout p95 latency", "95% of checkouts finish faster than this (last 5 min).",
     'histogram_quantile(0.95, sum by (le) (rate(http_server_duration_milliseconds_bucket{service_name="gateway"}[5m])))',
     "ms", 6, 1, [{"color": G, "value": None}, {"color": Y, "value": 300}, {"color": R, "value": 500}])
stat("Orders per minute", "Paid orders per minute.", 'sum(rate(shop_orders_total{status="paid"}[5m])) * 60',
     "short", 12, 1, [{"color": "blue", "value": None}])
stat("Revenue per minute", "Sum of paid order values per minute.", 'sum(rate(shop_order_value_USD_sum[5m])) * 60',
     "currencyUSD", 18, 1, [{"color": "blue", "value": None}])

row("RED metrics per service (Rate, Errors, Duration)", 5)
ts("Rate: requests / s", "Incoming HTTP requests per second, per service.",
   [{"expr": f'sum by (service_name) (rate(http_server_duration_milliseconds_count{{{SEL}}}[1m]))', "legendFormat": "{{service_name}}"}],
   "reqps", 0, 6)
ts("Errors: 5xx %", "Share of requests that returned a 5xx status.",
   [{"expr": f'100 * (sum by (service_name) (rate(http_server_duration_milliseconds_count{{{SEL},http_status_code=~"5.."}}[1m])) or sum by (service_name) (rate(http_server_duration_milliseconds_count{{{SEL}}}[1m])) * 0) / sum by (service_name) (rate(http_server_duration_milliseconds_count{{{SEL}}}[1m]))', "legendFormat": "{{service_name}}"}],
   "percent", 8, 6, extra={"min": 0})
ts("Duration: p50 / p95 / p99", "Latency percentiles per service. Dots are exemplars: click one to open that exact trace.",
   [{"expr": f'histogram_quantile({q}, sum by (le, service_name) (rate(http_server_duration_milliseconds_bucket{{{SEL}}}[1m])))',
     "legendFormat": f"{{{{service_name}}}} p{int(q*100)}", "exemplar": True} for q in (0.5, 0.95, 0.99)],
   "ms", 16, 6)

row("Business metrics", 14)
ts("Orders by status", "Orders per second, split by final status (from the custom shop.orders counter).",
   [{"expr": 'sum by (status) (rate(shop_orders_total[1m]))', "legendFormat": "{{status}}"}], "short", 0, 15, w=12)
ts("Order value", "Median and 95th percentile order value (from the custom shop.order.value histogram).",
   [{"expr": f'histogram_quantile({q}, sum by (le) (rate(shop_order_value_USD_bucket[5m])))', "legendFormat": f"p{int(q*100)}"} for q in (0.5, 0.95)],
   "currencyUSD", 12, 15, w=12)

row("Traces and logs", 23)
add({"type": "nodeGraph", "title": "Service map", "description": "Built by Tempo from spans: who calls whom, request rate and error share.",
     "datasource": T, "targets": [{"datasource": T, "refId": "A", "queryType": "serviceMap"}], "options": {}}, 0, 24, 12, 10)
add({"type": "table", "title": "Recent failed or slow traces", "description": "TraceQL: spans with error status or slower than 300 ms. Click a trace ID to open it.",
     "datasource": T, "targets": [{"datasource": T, "refId": "A", "queryType": "traceql", "query": '{ status = error || duration > 300ms }', "limit": 20, "tableType": "traces"}],
     "options": {"showHeader": True}}, 12, 24, 12, 10)
add({"type": "logs", "title": "Warnings and errors", "description": "Logs from all shop services at WARN or above. Expand a line and use 'View trace' to jump to Tempo.",
     "datasource": L, "targets": [{"datasource": L, "refId": "A", "expr": '{service_namespace="shop", service_name=~"$service"} | severity_number >= 13'}],
     "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending", "enableLogDetails": True}}, 0, 34, 24, 10)

dash = {
    "uid": "shop-overview", "title": "Shop overview", "tags": ["shop", "opentelemetry"],
    "timezone": "browser", "schemaVersion": 39, "version": 1, "refresh": "10s",
    "time": {"from": "now-15m", "to": "now"},
    "templating": {"list": [{
        "name": "service", "label": "Service", "type": "query", "datasource": P,
        "query": {"query": "label_values(http_server_duration_milliseconds_count, service_name)", "refId": "q"},
        "definition": "label_values(http_server_duration_milliseconds_count, service_name)",
        "multi": True, "includeAll": True, "allValue": ".*",
        "current": {"text": ["All"], "value": ["$__all"]}, "refresh": 2}]},
    "annotations": {"list": []},
    "panels": panels,
}
with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(dash, out, indent=2)
    out.write("\n")
print(len(panels), "panels")
