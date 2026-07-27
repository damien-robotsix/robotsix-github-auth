## 0.0.0 (unreleased)

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
