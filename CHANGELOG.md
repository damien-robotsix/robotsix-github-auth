## 0.0.0 (unreleased)

- `validate_scopes` now raises `ValueError` (instead of folding into `ScopeError`) when the *required* minimum level is not one of `read`/`write`/`admin` — a caller configuration error. Token-side unknown levels continue to fail closed as `ScopeError`.
- Upgrade transitive `cryptography` dependency from 49.0.0 to 50.0.0 (GHSA-g6cj-pr64-35w5)
- `InstallationToken.is_expired` is now a method accepting an optional `margin_seconds` parameter (default 0.0), replacing the parameterless property. The token cache now dogfoods this API via `is_expired(margin_seconds=_REFRESH_MARGIN_SECONDS)` instead of a raw `seconds_remaining` comparison.
- Add `.robotsix-mill/config.yaml` with `languages: [python]` to declare the repo's language scope for robotsix-mill periodic agents.
- Add single-flight request coalescing to `mint_installation_token` so that
  concurrent callers for the same `(installation_id, scopes)` share a single
  upstream token-mint call instead of each firing a redundant
  `POST /app/installations/{id}/access_tokens` to GitHub.
- Add `py.typed` PEP 561 marker and `Typing :: Typed` trove classifier for downstream type-checker discoverability.
- Document `invalidate_token_cache` and `clear_token_cache` in the README API reference section.
- Wire up `_close_github_client()` via `atexit.register()` so the persistent httpx client is closed on interpreter shutdown.
- Adopt a persistent `httpx.Client` with an explicit 10s timeout in `_auth.py` for connection reuse and deterministic timeouts.
- Replace bare `assert` with explicit `if`/`raise` in `_auth.py` to avoid silent failure under `python -O`.
- Move `docs/ci-conventions.md` to per-module `docs/ci/ci-conventions.md` and register `docs/ci/**` under the `ci` module in `docs/modules.yaml`.
- Move `tests/test_ci_conventions.py` to per-module layout at `tests/scripts/test_ci_conventions.py` and update relative path resolution
- Reorganize test files into per-module `tests/core/` directory (pure `git mv`; no import or test-body changes).
- Fix token-expiry datetime parsing: use `.astimezone(UTC)` instead of `.replace(tzinfo=UTC)` to preserve the absolute instant when converting non-UTC offsets.
- Enable `module_curator` and `module_size` periodic workflows.
- Document CI workflow conventions in README: `persist-credentials: false` on every checkout step, `setup-uv` before any `uv` command, and mirror existing job conventions for new jobs.
- Add CI workflow convention validation: new `scripts/check_ci_conventions.py` checks that every job in `.github/workflows/ci.yml` follows shared step patterns (harden-runner first, `persist-credentials: false` on checkout, `astral-sh/setup-uv` when using uv), and a `ci-conventions` CI job enforces these rules on every push and PR.
- Extracted `astral-sh/setup-uv` into a local composite action at `.github/actions/setup` to reduce duplication across all CI jobs. (harden-runner and `actions/checkout` were intentionally kept at job level because a local composite action cannot be resolved before checkout runs.)
- Add `.pre-commit-config.yaml` with pre-commit-hooks (file sanity), ruff (lint + format), and mypy (pre-push type-checking)
- Wrap `resp.json()` calls in `_resolve_installation_id` and `_mint_token` inside the existing try/except blocks so that `JSONDecodeError` (e.g. from a proxy injecting an HTML error page) is caught and wrapped in `TokenMintError` instead of leaking as a bare exception.)
- `_mint_token()` now wraps all response-parse failure points in `TokenMintError` — missing `"token"` key and invalid ISO-8601 `expires_at` no longer leak bare `KeyError` / `ValueError`.
- Fix cache bypass in `mint_installation_token()` when called with `owner`/`repo` — the cache is now checked after resolving the installation ID, preventing unnecessary token-minting API calls.
- Adopt `robotsix-modules` for module registration: add as dev dependency,
  create `docs/modules.yaml` classifying all source modules, and add
  module validation job to CI. Bump `requires-python` to `>=3.14` (required by
  robotsix-modules) and update CI matrix accordingly.
- Enable `copy_paste` periodic workflow (jscpd duplicate detection).
- Expose `invalidate_token_cache()` and `clear_token_cache()` as public API in `robotsix_github_auth` so callers can manage the token cache without importing private internals.
- Enable the `survey` periodic workflow in `.robotsix-mill/periodic/survey.yaml`.
- Enable `bc_check` periodic workflow for backward-compatibility hygiene scanning.
- Enable `repo_description_sync` periodic workflow to keep the GitHub repo description aligned with README.
- Enable `completeness_check` periodic workflow to scan for incomplete feature wiring.
- Register `docstring_coverage` periodic workflow config (`.robotsix-mill/periodic/docstring_coverage.yaml`).
- Upgrade pytest from 8.4.2 to 9.1.1 to fix CVE-2025-71176 (PYSEC-2026-1845, GHSA-6w46-j5rx-g56g), a predictable `/tmp` directory vulnerability.
- Add code coverage measurement and enforcement: `pytest-cov` dev dependency, `[tool.coverage]` config with branch coverage at 80% threshold, and `--cov --cov-fail-under=80` in CI test step.
- `_mint_token` now raises `TokenMintError` (instead of a bare `KeyError`) when the GitHub API response is missing the `expires_at` field, improving error diagnostics.
- Remove unused `ttl_seconds` parameter from `mint_installation_token`. The parameter
  was never forwarded to the GitHub API; callers who passed it were silently ignored.
- Removed unused `repositories` parameter from private `_mint_token` function (no callers ever passed it).
- Enable periodic `audit` workflow for comprehensive codebase health reviews.
- Enable periodic test-gap analysis agent to detect coverage regressions and
  propose draft tickets for under-tested modules.
- Enable the `health` periodic workflow (`.robotsix-mill/periodic/health.yaml`), which inspects the repository across eight dimensions and proposes draft tickets for newly-discovered gaps.
- Enable `changelog_autofill` periodic workflow to automate changelog entry creation and bundling.
- Adopt `robotsix-http` for retry/backoff on GitHub API calls. Replaced bare
  `httpx.Client()` with `robotsix_http.call_with_retry` using `RetryConfig(max_retries=2)`.
  Bumped `requires-python` to `>=3.12` to match the `robotsix-http` dependency.
- Initial release: fleet-wide GitHub App installation-token minting library.
  - `mint_installation_token()` — build App JWT (RS256), resolve installation ID from owner/repo, mint tokens via GitHub REST API, with optional permission narrowing.
  - `InstallationToken` dataclass with `token`, `expires_at`, `permissions`, `seconds_remaining`, and `is_expired`.
  - Thread-safe in-process cache keyed by `(installation_id, scope-set)` with 5-minute refresh margin.
  - `validate_scopes()` helper with hierarchical permission checking (`admin` > `write` > `read`).
  - Typed exceptions: `GithubAuthError`, `TokenMintError`, `ScopeError`.
  - Full unit test suite (38 tests) with mocked HTTP.
