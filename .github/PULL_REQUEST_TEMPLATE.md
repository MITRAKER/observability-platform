## What

<!-- What does this change and why? Link the issue: "Closes #123". -->

## How it was tested

<!-- Commands you ran, dashboards you checked, screenshots. -->

## Checklist

- [ ] `ruff check . && ruff format --check .` pass
- [ ] `mypy` and `python tools/check_power_of_ten.py` pass
- [ ] `pytest --cov` passes and coverage did not drop
- [ ] New alerts or rules have a `promtool` unit test and a runbook entry
- [ ] `LEARNING.md`, `README.md` and `CHANGELOG.md` updated if behaviour changed
