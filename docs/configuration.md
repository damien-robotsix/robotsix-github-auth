# Configuration reference

The library reads configuration from function arguments first and environment
variables second.  Only `github_token` and `github_push_token` consult
environment variables; `mint_installation_token` and
`resolve_installation_id_for_repo` take explicit arguments only.

## Environment variables

| Variable | Default | Meaning | Used by |
|---|---|---|---|
| `GITHUB_AUTH_MODE` | `app` | Auth mode: `token` (PAT) or `app` (GitHub App). Any other value raises `TokenMintError`. | `github_token`, `github_push_token` |
| `FORGE_TOKEN` | — | Primary personal access token (token mode). | `github_token`, `github_push_token` (fallback) |
| `FORGE_PUSH_TOKEN` | — | Push-specific PAT (token mode); falls back to `FORGE_TOKEN`. | `github_push_token` |
| `GITHUB_APP_ID` | — | GitHub App ID (app mode). | `github_token` (and `github_push_token` in app mode) |
| `GITHUB_APP_PRIVATE_KEY` | — | PEM-encoded RSA private key of the App (app mode). | `github_token` (and `github_push_token` in app mode) |
| `GITHUB_APP_INSTALLATION_ID` | — | Static installation ID (app mode). Used directly when `owner`/`repo` are not given; otherwise only as a fallback when per-repo resolution is unavailable. | `github_token` (and `github_push_token` in app mode) |

## Precedence

For every setting an explicit, non-empty argument wins over the environment
variable:

| Argument | Environment fallback |
|---|---|
| `auth_mode` | `GITHUB_AUTH_MODE`, else `"app"` |
| `pat` | `FORGE_TOKEN` |
| `push_token` | `FORGE_PUSH_TOKEN`, then `pat`, then `FORGE_TOKEN` |
| `app_id` | `GITHUB_APP_ID` |
| `private_key` | `GITHUB_APP_PRIVATE_KEY` |
| `installation_id` | `GITHUB_APP_INSTALLATION_ID` |

`owner`, `repo` and `scopes` have no environment fallback.

## Auth-mode behaviour

**Token mode** (`GITHUB_AUTH_MODE=token`):

* `github_token` returns `pat` / `FORGE_TOKEN`; raises `TokenMintError` if unset.
* `github_push_token` returns `push_token` / `FORGE_PUSH_TOKEN`, falling back to
  `pat` / `FORGE_TOKEN`; raises `TokenMintError` if none is set.
* No network calls are made and `scopes` / App parameters are ignored.

**App mode** (default):

* An installation token is minted (or served from cache) and its string returned.
* Either `owner` + `repo` or an installation id must be available.  With
  `owner` + `repo` the installation id is resolved per repository; the static
  id is only a fallback (see [architecture.md](architecture.md)).
* `github_push_token` behaves exactly like `github_token`.

## Built-in defaults

These are fixed constants, not configurable at runtime:

| Setting | Value | Defined in |
|---|---|---|
| GitHub API base URL | `https://api.github.com` | `_auth.py` |
| HTTP timeout | 10 s | `_auth.py` |
| HTTP retries (`robotsix_http`) | 2 | `_auth.py` |
| App JWT lifetime | 600 s | `_auth.py` |
| App JWT clock-skew back-dating | 60 s | `_auth.py` |
| Token cache refresh margin | 300 s (tokens are re-minted when < 5 min remain) | `_cache.py` |
| Installation-id cache TTL | 300 s | `_cache.py` |
| `Retry-After` default | 60 s when missing or unparseable | `_auth.py` |
