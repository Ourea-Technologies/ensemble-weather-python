# The ensemble-weather SDK standard

Every official Ourea SDK repository follows this document. It fixes **what
every repository contains and how it is checked**. It does not fix the shape of
the public API. Each SDK expresses [BEHAVIOR.md](BEHAVIOR.md) in its own
language's idiom (epic KAN-1049; per-language conventions below).

## Names

| Language | Repository | Package | Install |
|---|---|---|---|
| Python | `ensemble-weather-python` | PyPI `ensemble-weather`, import `ensemble_weather` | `pip install ensemble-weather` |
| TypeScript / JS | `ensemble-weather-typescript` | npm `ensemble-weather` | `npm install ensemble-weather` |
| Go | `ensemble-weather-go` | module `oureawx.com/go/ensemble-weather`, package `ensembleweather` | `go get oureawx.com/go/ensemble-weather` |
| C# / .NET | `ensemble-weather-dotnet` | NuGet `EnsembleWeather`, namespace `EnsembleWeather` | `dotnet add package EnsembleWeather` |
| Java | `ensemble-weather-java` | Maven `com.oureawx:ensemble-weather`, module `com.oureawx.ensembleweather` | Maven / Gradle coordinates |
| Kotlin | `ensemble-weather-kotlin` | Maven `com.oureawx:ensemble-weather-kotlin`, package `com.oureawx.ensembleweather.kotlin` | Gradle coordinates |
| Swift | `ensemble-weather-swift` | SwiftPM product `EnsembleWeather` | `.package(url: "https://github.com/Ourea-Technologies/ensemble-weather-swift", from: "0.1.0")` |

The registry description of every package contains **"Ourea"** and its keywords
include `ourea`, `weather`, `forecast`, `ensemble` and `probabilistic`, so brand
searches find it.

## Repository layout

```
README.md            the quickstart (see "README")
LICENSE              BSD-2-Clause, "Copyright (c) 2026 Ourea Technologies"
CHANGELOG.md         Keep a Changelog; one entry per release
CONTRIBUTING.md      dev setup, how to run lint/tests/examples, commit style
SECURITY.md          private disclosure through GitHub private vulnerability reporting; no public issues
CODE_OF_CONDUCT.md   Contributor Covenant 2.1
.github/
  workflows/ci.yml        lint + type check + unit + vectors + examples (every push, PR)
  workflows/live.yml      nightly contract run against the live API (read-only key)
  workflows/release.yml   tag v*.*.* -> build, publish, GitHub release
  workflows/security.yml  dependency audit, static security lint, workflow audit (see "Security")
  workflows/codeql.yml    CodeQL (every SDK language is supported)
  workflows/scorecard.yml OpenSSF Scorecard, weekly + on main
  dependabot.yml          the package ecosystem + github-actions, weekly
  ISSUE_TEMPLATE/         bug report, feature request; config.yml links the docs
  pull_request_template.md
<source>             the language's standard layout (src/, lib/, Sources/, ...)
<tests>              unit tests + the shared vectors runner
examples/            runnable programs, one per task (see "Examples")
spec/                a pinned copy of ensemble-weather-spec at a tag (see "Spec pinning")
```

## README

Short, top to bottom, in this order. A developer must be able to make a first
successful call in **under 60 seconds** from the top of the README, with no
signup.

1. **Title + one line:** "Official <Language> SDK for the [Ourea](https://oureawx.com)
   probabilistic weather API." Then one row of badges, in this order:
   CI (`ci.yml` status on `main`), security (`security.yml` status on `main`),
   registry version, supported runtime versions where the ecosystem has a
   badge for them, licence (BSD-2-Clause), docs, and the OpenSSF Scorecard.
   Use shields.io or GitHub's own workflow badge URLs, linking each badge to
   its source (the workflow runs, the registry page, the docs).
2. **Install:** one command.
3. **Quickstart:** ONE copy-paste program, the same task in every language:
   an anonymous forecast for a named location (`or/mt-hood-meadows`), printing
   the next 24 h's temperature as a range (p10-p90) and the chance of at
   least 6 in (15 cm) of snow in the next 24 h. It runs without an API key.
   That exact code also lives in `examples/` and CI runs it, so the README can
   never rot.
4. **Authentication:** how to pass a key (constructor argument and the
   `OUREA_API_KEY` environment variable), and what Free, anonymous and Pro
   allow. Link the pricing page.
5. **Probabilities, not single numbers:** three short snippets (`chance`,
   window totals, quantiles), and the rule that the SDK never sums or
   interpolates quantiles itself because the server computes every
   probability from the full ensemble. Link https://docs.oureawx.com/concepts/probabilities.
6. **More examples:** a table linking each `examples/` file to one line of
   what it shows.
7. **Errors, retries and rate limits:** the error type(s), what is retried, how
   to read the rate-limit state.
8. **Documentation:** links to https://docs.oureawx.com (the guides),
   https://docs.oureawx.com/<lang> (this SDK's guide), the generated API
   reference (the ecosystem's own host: Read the Docs, pkg.go.dev, javadoc.io,
   ...), and the OpenAPI spec in ensemble-weather-spec.
9. **Supported versions:** the language/runtime versions CI tests.
10. **Contributing, security, licence:** one line each, linking the files.

Every link back to Ourea uses `https://oureawx.com` or
`https://docs.oureawx.com`. Never `api.oureawx.com` as a page, and never a dev
host.

## Examples

`examples/` holds small, complete programs. Each one is one file (or one
directory where the ecosystem needs a project file), has a header comment
saying what it shows, and CI runs it. Every SDK ships at least these, with the
same names in its own case style:

| Name | Shows |
|---|---|
| `quickstart` | the README program, anonymous |
| `point_forecast` | a forecast at coordinates with elevation (Pro key from `OUREA_API_KEY`; skipped in CI without one) |
| `chance_of_snow` | several `prob` terms in one call, with their windows and member counts |
| `storm_total` | `totals` window distributions for precipitation and snowfall |
| `search_and_catalog` | search, then page through the catalog with the cursor |
| `current_and_alerts` | current conditions and active alerts for a location |
| `error_handling` | catching an out-of-coverage error by its code; reading rate-limit state |
| `units` | the same forecast in metric and imperial |

Examples that need a Pro key detect a missing `OUREA_API_KEY`, print one line
saying so, and exit 0.

## Tests

- **Unit tests** in the ecosystem's standard framework, across the supported
  version matrix.
- **The shared vectors** (`spec/vectors/`, format in BEHAVIOR.md): every SDK
  runs every vector against a local mock transport. A vector the SDK cannot
  run is a failing test, not a skip.
- **Spec drift:** the models round-trip every example in the pinned
  `spec/openapi/v1/openapi.yaml`, and a test fails if the spec has an operation
  the SDK does not expose.
- **Live (nightly, `live.yml`):** the quickstart and a short contract run
  against `https://api.oureawx.com` with a read-only CI key from Actions
  secrets. It never runs on PRs from forks. The User-Agent is the SDK's own,
  with no personal data.
- Coverage is reported in CI. There is no hard gate before 1.0.

## Lint and format

Each ecosystem's standard tools, at their strictest common settings, fail CI:

| Language | Format | Lint / types |
|---|---|---|
| Python | ruff format | ruff (incl. `D`, `UP`, `B`, `ANN`), mypy `--strict` |
| TypeScript | prettier | eslint (typescript-eslint strict-type-checked), `tsc --noEmit` strict |
| Go | gofmt | go vet, staticcheck, golangci-lint (default + revive) |
| C# | dotnet format | .NET analyzers `AnalysisLevel=latest-recommended`, warnings as errors, nullable enabled |
| Java | google-java-format | Error Prone + NullAway, `-Xlint:all -Werror` |
| Kotlin | ktlint | detekt, explicit API mode |
| Swift | swift-format | swift-format lint `--strict`, Swift 6 strict concurrency |

## Dependencies

As few as possible. Every runtime dependency is a supply-chain risk and an
install-friction cost.

- **Runtime:** the standard library HTTP client and JSON wherever the
  language has a good one (TypeScript fetch, Go net/http, .NET HttpClient +
  System.Text.Json, Java java.net.http, Swift URLSession). Python uses httpx
  (the one allowed runtime dependency; it gives sync + async with one API).
  Kotlin may use kotlinx-coroutines and kotlinx-serialization. Anything else
  needs a written justification in CONTRIBUTING.md and Harrison's approval.
- **Optional integrations** (pandas, xarray, DI containers) are extras or
  separate packages, never imported by the core.
- **Dev dependencies** are pinned through a lockfile (uv.lock,
  package-lock.json, go.sum, packages.lock.json, Gradle lockfile/version
  catalog, Package.resolved).
- CI fails if a new runtime dependency appears without its justification
  line in CONTRIBUTING.md (a small script that compares the manifest with
  the list).

## Security

Each SDK repository runs `security.yml` on every push, every PR, and weekly:

| Language | Dependency audit | Static security lint |
|---|---|---|
| Python | pip-audit (against uv.lock) | ruff `S` (bandit rules) |
| TypeScript | `npm audit --audit-level=low --omit=dev` + osv-scanner | eslint-plugin-security, with no `eval`/`Function` |
| Go | govulncheck | gosec (through golangci-lint) |
| C# | `dotnet list package --vulnerable --include-transitive` (fails on any) | .NET security analyzers (CA2xxx/CA3xxx/CA5xxx as errors) |
| Java | osv-scanner on the resolved dependency tree | Error Prone + SpotBugs with Find Security Bugs |
| Kotlin | osv-scanner on the Gradle lockfile | detekt (incl. potential-bugs) + SpotBugs/Find Security Bugs on the JVM bytecode |
| Swift | osv-scanner on Package.resolved | swift-format lint plus a grep gate: no force unwraps (`!`) or `try!` outside tests |

All SDKs also run:

- **CodeQL** (`codeql.yml`) with the `security-extended` query suite;
- **zizmor** on `.github/workflows/` (workflow injection, over-broad
  permissions, unpinned actions);
- **Dependency Review** (`actions/dependency-review-action`) on PRs, failing
  on any vulnerable or non-permissively licensed new dependency;
- **OpenSSF Scorecard** (`scorecard.yml`), published, with its badge in the
  README.

On GitHub (repo settings): secret scanning and push protection, Dependabot
alerts and security updates, private vulnerability reporting.

These SDK behaviours are tested by the shared vectors and by each SDK's own
tests:

- the API key never appears in logs, errors, `repr`/`toString`, or
  exception messages;
- the key is never sent to another host on a redirect;
- TLS verification is never disabled by default, and there is no option to
  disable it;
- response bodies are size-bounded (a body over 64 MiB is an error, not an
  out-of-memory);
- JSON parsing never evaluates code and never deserialises to arbitrary
  types (no polymorphic deserialisation).

## CI

- `ci.yml` runs on push to `main` and on every PR: format check, lint, type
  check, unit tests (version matrix), the vectors, examples (anonymous ones
  against a local mock by default, so PRs need no secret), and the docs build.
- Actions are pinned by commit SHA. `permissions:` is `contents: read` by
  default, widened per job only where needed.
- `main` is protected: CI must pass, and history stays linear.

## Releases

- Semver. 0.x until each SDK passes its pre-1.0 review against its language's
  official guide (KAN-1049). The SDK version is independent of the API
  version; the README states the API contract version it targets (v1).
- Tag `vX.Y.Z` on `main` triggers `release.yml`. It builds, runs CI again, and
  publishes:
  - PyPI, npm (`--provenance`), NuGet: OIDC trusted publishing, with no stored
    tokens.
  - Maven Central (Java, Kotlin): the Central Portal, with signed artifacts;
    the namespace `com.oureawx` is verified by a DNS TXT record.
  - Go and Swift: the tag is the release. The Go vanity path is served from
    `https://oureawx.com/go/ensemble-weather?go-get=1`.
- Every release gets a GitHub release with the changelog section and, where
  the ecosystem supports it, an SBOM and build provenance.

## Spec pinning

`spec/` is a copy of this repository at a release tag, written by a script
(`scripts/sync-spec` in each SDK). CI fails if `spec/` differs from the tag it
names in `spec/VERSION`. When this repository tags a new spec, a workflow
opens a PR in each SDK repository bumping it, and that repository's CI gates
it.

## Generated code

Code generated from the OpenAPI spec, if a language uses it, stays internal.
The public surface is hand-written, idiomatic, and documented. Generated
files carry a header naming the generator and the spec version, plus the
BSD-2-Clause licence.
