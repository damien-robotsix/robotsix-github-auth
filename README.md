# robotsix-github-auth

Fleet-wide GitHub App authorization library: JWT signing + installation-token minting/caching + scope validation. Single shared implementation for all robotsix components. No secrets in-repo — minting logic only.

## Installation

```bash
pip install robotsix-github-auth
# or
uv add robotsix-github-auth
```

## Quick start

```python
from robotsix_github_auth import mint_installation_token

token = mint_installation_token(
    app_id="123456",
    private_key=open("my-app.pem").read(),
    installation_id="987654",
)
print(token.token)  # "ghs_…"
print(token.expires_at)  # 2026-07-22 10:30:00+00:00
```

### Resolving the installation ID from owner/repo

If you don't know the installation ID, pass `owner` and `repo` and the
library will resolve it automatically:

```python
token = mint_installation_token(
    app_id="123456",
    private_key=open("my-app.pem").read(),
    owner="my-org",
    repo="my-repo",
)
```

### Permission narrowing (scopes)

Request a token with reduced permissions:

```python
token = mint_installation_token(
    app_id="123456",
    private_key=open("my-app.pem").read(),
    installation_id="987654",
    scopes={"contents": "read", "issues": "write"},
)
```

### Caching

Tokens are cached in-process keyed by `(installation_id, scope-set)`.
Repeated calls with the same parameters return the cached token without
contacting GitHub.  Tokens are evicted when fewer than **5 minutes**
remain before expiry — the next call will transparently re-mint.

**Request coalescing.**  When multiple callers concurrently request a
token for the same `(installation_id, scopes)` key and no valid cached
token exists, only one upstream `POST /app/installations/{id}/access_tokens`
call is made.  The first caller mints the token while others wait (per-key
lock); once the mint completes, all waiters receive the same token.  If
the mint fails, the lock is released and each waiter retries independently.
Different installation IDs or scope-sets use separate locks and do not
block each other.

Callers that need to force a fresh token can clear the cache:

```python
from robotsix_github_auth import invalidate_token_cache, clear_token_cache

invalidate_token_cache("987654")  # clear one installation
clear_token_cache()  # clear everything
```

### Scope validation

Use `validate_scopes` to assert that a token has the permissions you need:

```python
from robotsix_github_auth import validate_scopes, ScopeError

required = {"contents": "write"}

try:
    validate_scopes(token.permissions, required)
except ScopeError as exc:
    print(f"Insufficient permissions: {exc.missing}")
```

Permission levels are hierarchical: `admin` > `write` > `read`.  A token
with `write` satisfies a `read` requirement.

## API reference

### `mint_installation_token`

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

Returns `InstallationToken`.  Raises `TokenMintError` on failure.

### `InstallationToken`

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

### `validate_scopes`

```python
def validate_scopes(
    token_permissions: Mapping[str, Any],
    required: Mapping[str, str],
) -> None
```

Raises `ScopeError` when a required permission is missing or insufficient.

### `invalidate_token_cache`

```python
def invalidate_token_cache(installation_id: str) -> None
```

Remove all cached tokens for the given installation ID.

### `clear_token_cache`

```python
def clear_token_cache() -> None
```

Remove every cached token.

### Exceptions

| Exception | Base | Description |
|---|---|---|
| `GithubAuthError` | `Exception` | Base for all library errors. |
| `TokenMintError` | `GithubAuthError` | JWT signing failure, HTTP error, missing params. |
| `ScopeError` | `GithubAuthError` | Token permissions insufficient. Has `.missing: list[str]`. |

## Exceptions / Out-of-scope

1. **Repo creation is NOT covered.**  GitHub Apps cannot create
   personal-account repositories.  `central-deploy` retains its
   `github_repo_create_token` PAT as a permanent, justified exception.

2. **GHCR login flows** are out of scope.  This library only mints
   installation access tokens — not container-registry auth.

3. **Consumer migrations** are separate tickets.  This library is a
   dependency; each fleet component (central-deploy, mill, chat, CI)
   will migrate in its own change.

## Development

```bash
uv sync --dev
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run mypy src/
uv run deptry .
```

## CI workflow conventions

- **`persist-credentials: false`** — Every `actions/checkout` step in a
  CI job MUST include `persist-credentials: false` to suppress zizmor
  `artipacked` findings.

- **`setup-uv`** — Every CI job that invokes `uv` MUST include an
  `astral-sh/setup-uv` step before any `uv` command.

- **Mirror existing conventions** — New jobs should copy shared step
  conventions from existing jobs (runner hardening, checkout with
  `persist-credentials: false`, `setup-uv`, frozen sync).  See
  `.github/workflows/ci.yml` for the canonical template.

## License

MIT
