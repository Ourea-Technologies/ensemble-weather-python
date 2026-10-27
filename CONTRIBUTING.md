# Contributing to ensemble-weather

Thank you for helping. This is the official Python SDK for the
[Ourea](https://oureawx.com) API; its behaviour is fixed by the shared
[SDK spec](spec/BEHAVIOR.md) and [repository standard](spec/SDK-STANDARD.md),
and its public API follows Python's own conventions (PEP 8, PEP 257, PEP 484).

## Development setup

You need [uv](https://docs.astral.sh/uv/). It creates `.venv/` in the
repository and installs the locked dev and docs tools from `uv.lock`:

```sh
uv sync
```

## Checks

CI runs exactly these; run them before you push:

```sh
uv run ruff format --check .          # formatting
uv run ruff check .                   # lint: every ruff rule (incl. D, UP, B, ANN, S)
uv run mypy                           # type check, --strict
uv run pytest                         # unit tests, the shared vectors, the examples
uv run mkdocs build --strict          # the API reference
uv build                              # wheel and sdist
uv run python scripts/check_dependencies.py   # runtime dependencies are justified
scripts/sync-spec --check             # spec/ matches spec/VERSION
```

`pytest` runs every vector in `spec/vectors/` against both `Client` and
`AsyncClient` through an `httpx.MockTransport`, and runs every program in
`examples/` against a local stub server (`tests/stub_server.py`). Tests never
call the real API. To run one example by hand, start the stub and point the
SDK at it:

```sh
uv run python tests/stub_server.py              # prints: export OUREA_BASE_URL=...
OUREA_BASE_URL=http://127.0.0.1:PORT uv run python examples/quickstart.py
```

## The spec

`spec/` is a copy of
[ensemble-weather-spec](https://github.com/Ourea-Technologies/ensemble-weather-spec)
at the commit or tag in `spec/VERSION`. Never edit it by hand:

```sh
scripts/sync-spec v1.1.0     # pin a new spec version and copy it in
```

If a vector looks wrong, open an issue on the spec repository instead of
bending the SDK to it.

## Rules of the road

- The server computes, the SDK carries: no summing, averaging or
  interpolating of quantiles, and no probabilities derived client-side.
- Every bug fix comes with a test that fails without it.
- Every public name has a docstring (Google style) and full type hints.
- Commit messages: an imperative summary line (`Add`, `Fix`, ...) of at most
  72 characters, a blank line, then what changed and why. One logical change
  per commit; `main` has a linear history.

## Dependencies

As few as possible: each runtime dependency is a supply-chain risk and an
install cost. `scripts/check_dependencies.py` (run in CI) fails if
`pyproject.toml` declares a runtime dependency or extra that is not listed
here with its justification. Adding one needs the maintainers' approval.

### Runtime dependencies

- `httpx`: the HTTP client. The standard library has no async HTTP client,
  and httpx gives `Client` and `AsyncClient` one API, connection pooling,
  timeouts, streaming (for the 64 MiB response bound) and a mock transport
  for tests. It is the one allowed runtime dependency (SDK-STANDARD).

### Optional extras

- `pandas` (extra `pandas`): `to_dataframe()` views of a forecast. Imported
  only when one of those methods is called; the core never imports it.

Development tools (ruff, mypy, pytest, mkdocs, ...) are pinned in `uv.lock`
and never ship to users.

## Releasing (maintainers)

1. Update `CHANGELOG.md` and `src/ensemble_weather/_version.py`.
2. Merge to `main`, then tag `vX.Y.Z` on it and push the tag.
3. `release.yml` builds, tests, and publishes to PyPI through trusted
   publishing (OIDC, with attestations), then creates the GitHub release.
