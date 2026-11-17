# Security policy

## Reporting a vulnerability

Please do **not** open a public issue. Report it privately through
[GitHub security advisories](https://github.com/MITRAKER/observability-platform/security/advisories/new).
You will get an answer within 7 days.

## Scope and known demo settings

This is a learning project. Some settings are deliberately unsafe for
production and are marked as such in the code:

- Grafana allows anonymous admin access (`docker-compose.yml`).
- Backends (Prometheus, Loki, Tempo, Alertmanager) have no authentication.
- The payments chaos endpoint (`POST /chaos`) is unauthenticated.

## How the code is kept safe

- Dependencies are pinned, scanned with `pip-audit` on every PR, and updated by Dependabot.
- `gitleaks` scans for committed secrets; CodeQL and ruff's Bandit rules scan the code.
- Containers run as a non-root user.
