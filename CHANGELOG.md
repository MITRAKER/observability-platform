# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] - 2026-11-17

### Added
- Release workflow: tagging `vX.Y.Z` publishes all images to GitHub Container Registry and creates a GitHub release.
- Dependabot, pre-commit hooks, issue and PR templates, CODEOWNERS, CONTRIBUTING, SECURITY, `.editorconfig`.
- README badges and an architecture diagram.

## [0.5.0] - 2026-11-17

### Added
- CI: ruff, mypy `--strict`, Power of Ten checker, 54 unit tests (99% coverage), pip-audit, gitleaks, config validation, hadolint, shellcheck, full-stack smoke test, CodeQL.

### Changed
- All Python code follows the NASA/JPL Power of Ten rules: bounded loops and memory, validated inputs, checked results, small functions.
- Containers run as a numeric non-root user.

## [0.4.0] - 2026-11-17

### Added
- Checkout SLOs (99% availability, 95% under 250 ms) with multi-window, multi-burn-rate alerts and promtool unit tests.
- Alertmanager, a webhook alert sink, an SLO dashboard, chaos scenarios and runbooks.

## [0.3.0] - 2026-11-17

### Added
- Prometheus, Tempo and Loki backends; Grafana with provisioned data sources, cross-signal links and the Shop overview dashboard.

## [0.2.0] - 2026-11-17

### Added
- OpenTelemetry auto-instrumentation, custom spans and metrics, trace-correlated logs, and an OpenTelemetry Collector.

## [0.1.0] - 2026-11-17

### Added
- Gateway, orders and payments services, a load generator and Docker Compose.

[Unreleased]: https://github.com/MITRAKER/observability-platform/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/MITRAKER/observability-platform/releases/tag/v0.6.0
[0.5.0]: https://github.com/MITRAKER/observability-platform/releases/tag/v0.5.0
[0.4.0]: https://github.com/MITRAKER/observability-platform/releases/tag/v0.4.0
[0.3.0]: https://github.com/MITRAKER/observability-platform/releases/tag/v0.3.0
[0.2.0]: https://github.com/MITRAKER/observability-platform/releases/tag/v0.2.0
[0.1.0]: https://github.com/MITRAKER/observability-platform/releases/tag/v0.1.0
