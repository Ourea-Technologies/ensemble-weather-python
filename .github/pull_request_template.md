## What and why

<!-- What does this change, and why? Link the issue. -->

## Checklist

- [ ] `uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest` pass
- [ ] A regression test fails without this change (for fixes)
- [ ] Public names have docstrings and type hints; docs build (`uv run mkdocs build --strict`)
- [ ] No new runtime dependency (or it is justified in CONTRIBUTING.md and approved)
- [ ] The SDK still computes no statistics (no summing or interpolating quantiles)
- [ ] CHANGELOG.md updated under "Unreleased"
