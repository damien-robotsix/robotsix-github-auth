# API reference

Full reference for the public API of `robotsix_github_auth`.  For a
consolidated list of environment variables and defaults see
[configuration.md](configuration.md); for the internal design see
[architecture.md](architecture.md).

## `mint_installation_token`

```python
def mint_installation_token(
    app_id: str,
    private_key: str,
    installation_id: str | None = None,
    *,
    owner: str | None = None,
    repo: str | None = None,
    scopes: Mapping[str, str] | None = None,
) -> InstallationToken
```

| Parameter | Description |
|---|---|
| `app_id` | The GitHub App ID. |
| `private_key` | PEM-encoded RSA private key for the App. |
| `installation_id` | Installation ID. If `None`, `owner`/`repo` are used to resolve it. |
| `owner` | Repository owner (org or user). Required when `installation_id` is `None`. |
| `repo` | Repository name. Required when `installation_id` is `None`. |
| `scopes` | Optional `{permission: level}` map to narrow the token. |

Returns `InstallationToken`.  Raises `TokenMintError` on failure, or `RateLimitError`
(respectively a subclass of `TokenMintError`) when GitHub returns a **429** rate-limit
response.

## `resolve_installation_id_for_repo`

```python
def resolve_installation_id_for_repo(
    *,
    owner: str,
    repo: str,
    app_id: str,
    private_key: str,
) -> str
```

Resolve and cache the GitHub App installation id covering `owner/repo`.  Builds a
short-lived App JWT and resolves the current installation id via the installations
API, caching it in-process (short TTL) so repeated calls for the same repo do not
re-hit the API.  Returns the installation id as a string.  Raises `TokenMintError`
on failure, `RepoNotInstalledError` when the App is not installed on the repository,
or `RateLimitError` on a **429** response.

## `InstallationToken`

```python
@dataclass
class InstallationToken:
    token: str
    expires_at: datetime  # UTC-aware
    permissions: dict[str, str]

    @property
    def seconds_remaining(self) -> float: ...
    def is_expired(self, margin_seconds: float = 0.0) -> bool: ...
```

## `validate_scopes`

```python
def validate_scopes(
    token_permissions: Mapping[str, Any],
    required: Mapping[str, str],
) -> None
```

Raises `ScopeError` when a required permission is missing or insufficient.

## `invalidate_token_cache`

```python
def invalidate_token_cache(installation_id: str) -> None
```

Remove all cached tokens for the given installation ID.

## `clear_token_cache`

```python
def clear_token_cache() -> None
```

Remove every cached token.

## `github_token`

```python
def github_token(
    *,
    pat: str | None = None,
    app_id: str | None = None,
    private_key: str | None = None,
    installation_id: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
    scopes: Mapping[str, str] | None = None,
    auth_mode: str | None = None,
) -> str
```

Resolve a GitHub bearer token using PAT or GitHub App authentication.

In **token** mode (`auth_mode="token"`, or `GITHUB_AUTH_MODE=token`) the token
is read from `pat` (falling back to the `FORGE_TOKEN` environment variable).  In
**app** mode (the default) the token is minted via the GitHub App and its raw
token string is returned.

| Parameter | Description |
|---|---|
| `pat` | Personal access token (PAT mode). Falls back to `FORGE_TOKEN`. |
| `app_id` | GitHub App ID (App mode). Falls back to `GITHUB_APP_ID`. |
| `private_key` | App private key PEM (App mode). Falls back to `GITHUB_APP_PRIVATE_KEY`. |
| `installation_id` | App installation ID (App mode). Falls back to `GITHUB_APP_INSTALLATION_ID`. |
| `owner` | Repository owner for installation resolution (App mode). |
| `repo` | Repository name for installation resolution (App mode). |
| `scopes` | Permission narrowing for the installation token (App mode). |
| `auth_mode` | `"token"` or `"app"`. Defaults to `GITHUB_AUTH_MODE` env var, else `"app"`. |

Returns the token as a string.  Raises `TokenMintError` when no token can be
resolved, or `RateLimitError` (a subclass of `TokenMintError`) on a **429**
response.

## `github_push_token`

```python
def github_push_token(
    *,
    pat: str | None = None,
    push_token: str | None = None,
    app_id: str | None = None,
    private_key: str | None = None,
    installation_id: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
    scopes: Mapping[str, str] | None = None,
    auth_mode: str | None = None,
) -> str
```

Resolve a GitHub bearer token suitable for push operations.

In **token** mode returns `push_token` (falling back to `FORGE_PUSH_TOKEN`),
then to the primary PAT (from `pat` or `FORGE_TOKEN`).  In **app** mode it
delegates to `github_token`.

| Parameter | Description |
|---|---|
| `pat` | Primary personal access token, used as fallback when `push_token` is unset (PAT mode). |
| `push_token` | Push-specific PAT (PAT mode). Falls back to `FORGE_PUSH_TOKEN`. |
| `app_id` | GitHub App ID (App mode). Falls back to `GITHUB_APP_ID`. |
| `private_key` | App private key PEM (App mode). Falls back to `GITHUB_APP_PRIVATE_KEY`. |
| `installation_id` | App installation ID (App mode). Falls back to `GITHUB_APP_INSTALLATION_ID`. |
| `owner` | Repository owner for installation resolution (App mode). |
| `repo` | Repository name for installation resolution (App mode). |
| `scopes` | Permission narrowing for the installation token (App mode). |
| `auth_mode` | `"token"` or `"app"`. Defaults to `GITHUB_AUTH_MODE` env var, else `"app"`. |

Returns the token as a string.  Raises `TokenMintError` when no token can be
resolved, or `RateLimitError` (a subclass of `TokenMintError`) on a **429**
response.

## Environment variables

`github_token` and `github_push_token` are configured primarily through
environment variables, with explicit function arguments taking precedence.  Both
select between **PAT** and **GitHub App** modes via `GITHUB_AUTH_MODE`.

| Variable | Meaning | Used by |
|---|---|---|
| `GITHUB_AUTH_MODE` | Auth mode: `"token"` (PAT) or `"app"` (default). | `github_token`, `github_push_token` |
| `FORGE_TOKEN` | Primary personal access token (PAT mode). | `github_token`, `github_push_token` |
| `FORGE_PUSH_TOKEN` | Push-specific PAT (PAT mode); falls back to `FORGE_TOKEN`. | `github_push_token` |
| `GITHUB_APP_ID` | GitHub App ID (App mode). | `github_token`, `github_push_token` |
| `GITHUB_APP_PRIVATE_KEY` | App private key PEM (App mode). | `github_token`, `github_push_token` |
| `GITHUB_APP_INSTALLATION_ID` | App installation ID (App mode); overrides per-repo resolution. | `github_token`, `github_push_token` |

**PAT → App fallback priority.** When `GITHUB_AUTH_MODE` is unset (the default)
or set to `"app"`, the GitHub App path is used.  Set `GITHUB_AUTH_MODE=token` to
use a PAT instead.  In token mode, `github_token` reads the primary PAT from
`FORGE_TOKEN` (or its `pat` argument); `github_push_token` prefers
`FORGE_PUSH_TOKEN` and falls back to `FORGE_TOKEN`.

## Exceptions

| Exception | Base | Description |
|---|---|---|
| `GithubAuthError` | `Exception` | Base for all library errors. |
| `TokenMintError` | `GithubAuthError` | JWT signing failure, HTTP error, missing params. |
| `RateLimitError` | `TokenMintError` | GitHub API 429 (rate limit) response. Has `.retry_after_seconds: int`. |
| `RepoNotInstalledError` | `TokenMintError` | The App is not installed on the target repo (installation lookup returned 404). Has `.owner: str` and `.repo: str`. |
| `ScopeError` | `GithubAuthError` | Token permissions insufficient. Has `.missing: list[str]`. |

## Handling rate limits

When GitHub returns a **429** rate-limit response, the library raises
`RateLimitError` (a subclass of `TokenMintError`, so existing handlers that
catch `TokenMintError` keep working).  It parses the `Retry-After` header into
seconds so callers can implement backoff:

```python
from robotsix_github_auth import RateLimitError, mint_installation_token

try:
    token = mint_installation_token(app_id, private_key, installation_id="987654")
except RateLimitError as exc:
    print(f"Rate limited; retry in {exc.retry_after_seconds}s")
    # schedule a retry after exc.retry_after_seconds
```

A simple backoff loop that honours `retry_after_seconds`:

```python
import time

from robotsix_github_auth import RateLimitError, mint_installation_token


def mint_with_backoff(app_id, private_key, *, installation_id, attempts=5):
    for attempt in range(attempts):
        try:
            return mint_installation_token(app_id, private_key, installation_id=installation_id)
        except RateLimitError as exc:
            if attempt == attempts - 1:
                raise
            time.sleep(exc.retry_after_seconds)
    raise RuntimeError("unreachable")  # pragma: no cover
```

`retry_after_seconds` accepts an integer number of seconds or an HTTP-date in
`Retry-After`, defaulting to **60** seconds when the header is missing or
unparseable.
