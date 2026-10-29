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

## Documentation

| Document | Contents |
|---|---|
| [docs/api.md](docs/api.md) | API reference: every public function, `InstallationToken`, exceptions, rate-limit handling. |
| [docs/configuration.md](docs/configuration.md) | Environment variables, parameters, defaults and auth-mode behaviour. |
| [docs/architecture.md](docs/architecture.md) | Module layout and the installation-resolution / token-mint flow. |
| [docs/migration.md](docs/migration.md) | Migration guide for the `RateLimitError` breaking change (0.5.0). |

Public entry points: `mint_installation_token`, `resolve_installation_id_for_repo`,
`github_token`, `github_push_token`, `validate_scopes`, `invalidate_token_cache`
and `clear_token_cache`.  All errors derive from `GithubAuthError`; GitHub **429**
responses raise `RateLimitError` (a `TokenMintError` subclass exposing
`retry_after_seconds`) — see [Handling rate limits](docs/api.md#handling-rate-limits).

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

See [CONTRIBUTING.md](CONTRIBUTING.md) for a full contributor guide:
environment setup, running tests and coverage, code style and type
checking, commit conventions, and pull-request guidelines.

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
