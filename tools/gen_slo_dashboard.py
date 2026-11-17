import json, sys
P = {"type": "prometheus", "uid": "prometheus"}
panels = []
def add(p, x, y, w, h):
    p["id"] = len(panels) + 1
    p["gridPos"] = {"x": x, "y": y, "w": w, "h": h}
    p.setdefault("datasource", P)
    panels.append(p)
def tgt(expr, legend="", **kw):
    return dict({"expr": expr, "legendFormat": legend, "datasource": P}, **kw)
def stat(title, desc, expr, unit, steps, x, y, kind="stat", mn=None, mx=None):
    d = {"unit": unit, "decimals": 2, "color": {"mode": "thresholds"},
         "thresholds": {"mode": "absolute", "steps": steps}}
    if mn is not None: d["min"] = mn
    if mx is not None: d["max"] = mx
    add({"type": kind, "title": title, "description": desc, "targets": [dict(tgt(expr), refId="A")],
         "fieldConfig": {"defaults": d, "overrides": []},
         "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background"}}, x, y, 6, 6)
def ts(title, desc, targets, unit, x, y, w=12, h=8, thresholds=None):
    d = {"unit": unit, "custom": {"fillOpacity": 5, "showPoints": "never",
         "thresholdsStyle": {"mode": "line+area" if thresholds else "off"}}}
    if thresholds:
        d["thresholds"] = {"mode": "absolute", "steps": thresholds}
        d["color"] = {"mode": "palette-classic"}
    add({"type": "timeseries", "title": title, "description": desc,
         "targets": [dict(t, refId=chr(65 + i)) for i, t in enumerate(targets)],
         "fieldConfig": {"defaults": d, "overrides": []},
         "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}}, x, y, w, h)

R, Y, G = "red", "orange", "green"
stat("Availability SLI (30d)", "Share of checkouts without a 5xx over 30 days. Objective: 99%.",
     "1 - slo:checkout_errors:ratio_rate30d", "percentunit",
     [{"color": R, "value": None}, {"color": G, "value": 0.99}], 0, 0)
stat("Availability error budget left", "1 = untouched, 0 = spent. Budget = 1% of requests may fail.",
     "slo:checkout_availability:error_budget_remaining", "percentunit",
     [{"color": R, "value": None}, {"color": Y, "value": 0.25}, {"color": G, "value": 0.5}], 6, 0, kind="gauge", mn=0, mx=1)
stat("Latency SLI (30d)", "Share of checkouts faster than 250 ms over 30 days. Objective: 95%.",
     "1 - slo:checkout_slow:ratio_rate30d", "percentunit",
     [{"color": R, "value": None}, {"color": G, "value": 0.95}], 12, 0)
stat("Latency error budget left", "1 = untouched, 0 = spent. Budget = 5% of requests may be slow.",
     "slo:checkout_latency:error_budget_remaining", "percentunit",
     [{"color": R, "value": None}, {"color": Y, "value": 0.25}, {"color": G, "value": 0.5}], 18, 0, kind="gauge", mn=0, mx=1)
ts("Availability burn rate", "How many times faster than 'sustainable' the error budget is being spent. Lines: 14.4x (fast-burn page) and 6x (slow-burn page).",
   [tgt("slo:checkout_errors:ratio_rate5m / 0.01", "5m"), tgt("slo:checkout_errors:ratio_rate1h / 0.01", "1h"),
    tgt("slo:checkout_errors:ratio_rate6h / 0.01", "6h")],
   "x", 0, 6, thresholds=[{"color": "transparent", "value": None}, {"color": Y, "value": 6}, {"color": R, "value": 14.4}])
ts("Latency burn rate", "Burn rate of the latency SLO. Line: 6x (page).",
   [tgt("slo:checkout_slow:ratio_rate5m / 0.05", "5m"), tgt("slo:checkout_slow:ratio_rate1h / 0.05", "1h")],
   "x", 12, 6, thresholds=[{"color": "transparent", "value": None}, {"color": R, "value": 6}])
add({"type": "table", "title": "Firing and pending alerts", "description": "From Prometheus' built-in ALERTS series.",
     "targets": [dict(tgt('ALERTS{alertstate=~"firing|pending"}', format="table", instant=True), refId="A")],
     "transformations": [{"id": "organize", "options": {"excludeByName": {"Time": True, "Value": True, "__name__": True}}}],
     "fieldConfig": {"defaults": {}, "overrides": []}, "options": {"showHeader": True}}, 0, 14, 24, 7)

dash = {"uid": "shop-slos", "title": "Shop SLOs", "tags": ["shop", "slo"], "timezone": "browser",
        "schemaVersion": 39, "version": 1, "refresh": "10s", "time": {"from": "now-30m", "to": "now"},
        "templating": {"list": []}, "annotations": {"list": []}, "panels": panels}
with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(dash, out, indent=2)
    out.write("\n")
print(len(panels))
