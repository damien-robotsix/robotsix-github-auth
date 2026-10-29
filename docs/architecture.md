# Architecture

`robotsix-github-auth` is a small, synchronous library that turns GitHub App
credentials (or a PAT) into a bearer token.  It holds no secrets itself: callers
provide the App id / private key (or PAT) via arguments or environment variables.

## Module layout

All implementation lives in private modules under `src/robotsix_github_auth/`;
`__init__.py` re-exports the public API.

| Module | Responsibility |
|---|---|
| `_auth.py` | Core flow: PAT/App mode selection (`github_token`, `github_push_token`), App JWT signing, per-repo installation-id resolution, installation-token minting, HTTP-error mapping and single-flight mint coalescing. Owns the shared `httpx.Client` (10 s timeout, closed at interpreter exit) and the env-var name constants. |
| `_cache.py` | Thread-safe in-process caches: `_TokenCache` keyed by `(installation_id, frozen scopes)` with a 5-minute refresh margin, and `_InstallationIdCache` keyed by `(owner, repo)` with a 5-minute TTL. |
| `_exceptions.py` | Exception hierarchy: `GithubAuthError` → `TokenMintError` → `RateLimitError` / `RepoNotInstalledError`, and `ScopeError`. |
| `_models.py` | `InstallationToken` dataclass (`token`, `expires_at`, `permissions`, expiry helpers). |
| `_scopes.py` | `validate_scopes`: hierarchical permission check (`admin` > `write` > `read`). |

## Token-mint flow (App mode)

`mint_installation_token` and `github_token` (App mode) both delegate to
`_resolve_token`:

1. **Validate inputs.** Either an `installation_id` or both `owner` and `repo`
   must be supplied, otherwise `TokenMintError`.
2. **Sign an App JWT** (`_build_app_jwt`): RS256, `iss=app_id`, issued 60 s in
   the past to absorb clock skew, valid for 600 s.
3. **Pick the installation id.**
   * Without `owner`/`repo`, the supplied `installation_id` is used as-is.
   * With `owner`/`repo`, the id is resolved per repository (see below).  If
     resolution fails with a transient `TokenMintError` (network, 5xx, rate
     limit) and a static `installation_id` was supplied, that id is used as a
     last-resort fallback.  `RepoNotInstalledError` is never masked.
4. **Mint with cache** (`_mint_with_cache`): return a cached token if one has
   more than 5 minutes left; otherwise acquire a per-key lock (same key as the
   cache), re-check the cache (double-checked locking) and call `_mint_token`,
   which `POST`s `/app/installations/{id}/access_tokens` with the optional
   `permissions` body.  Concurrent callers for the same key share one upstream
   request; distinct keys never block each other.
5. **Stale-id recovery.** If the mint returns HTTP 404 for an id resolved from
   `owner/repo`, the installation-id cache entry is invalidated, the id is
   re-resolved once and the mint retried.  A second 404 — or a 404 on the static
   fallback id — raises `RepoNotInstalledError`.

## Installation-resolution flow

`resolve_installation_id_for_repo` (public) and `_resolve_installation_id_for_repo`
(internal, reusing an existing JWT):

1. Check `_InstallationIdCache` for `(owner, repo)`; return on hit.
2. On a miss, `GET /repos/{owner}/{repo}/installation` with the App JWT.
3. Cache the returned `id` for 5 minutes.  A missing `id` or HTTP 404 raises
   `RepoNotInstalledError`.

Resolving per repository rather than trusting a statically configured id keeps
minting working after an account-wide App reinstall changes installation ids.

## HTTP error mapping

Both GitHub calls go through `robotsix_http.call_with_retry` (2 retries) and map
failures through a single helper, `_raise_for_github_error`:

| Failure | Raised |
|---|---|
| HTTP 429 | `RateLimitError` with `retry_after_seconds` parsed from `Retry-After` (seconds or HTTP-date; default 60) |
| HTTP 404 | `RepoNotInstalledError` (installation lookup) or internal `_MintNotFoundError` (mint, triggers stale-id recovery) |
| Other HTTP status | `TokenMintError` including the status code |
| Transport / decoding errors | `TokenMintError` including the original message |

## PAT mode

When the auth mode is `token`, no network call is made: `github_token` returns
the PAT and `github_push_token` returns the push PAT (falling back to the primary
PAT).  See [configuration.md](configuration.md).
