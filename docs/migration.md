# Migration guide (breaking change: new `RateLimitError`)

The rate-limit handling change introduces `RateLimitError` as a distinct error
type for GitHub **429** responses. Previously every HTTP error — including a
429 — was raised as a generic `TokenMintError` with no way to read the
`Retry-After` value. This is a **breaking change** for library users (it ships
in the next release, **0.5.0**).

## What changed

| Scenario | Before the change | After the change |
|---|---|---|
| Generic HTTP error (401, 403, 5xx, network, JWT) | `TokenMintError` | `TokenMintError` (unchanged) |
| 429 rate-limit response | `TokenMintError` | `RateLimitError` (subclass of `TokenMintError`) |
| `Retry-After` value | not exposed | `exc.retry_after_seconds` |

`RateLimitError` is a **subclass** of `TokenMintError`, so the change is
**additive**: existing `except TokenMintError` handlers keep working and still
catch 429s. No existing handler stops working.

## Steps to migrate

1. **Keep your existing `except TokenMintError` handler.** It continues to
   catch 429s, so nothing breaks by leaving it in place.

2. **Add a more specific `except RateLimitError` branch to implement backoff.**
   Order matters — the `RateLimitError` branch must come *before* the
   `TokenMintError` branch, otherwise the generic handler swallows the 429:

   ```python
   from robotsix_github_auth import RateLimitError, TokenMintError, mint_installation_token

   try:
       token = mint_installation_token(app_id, private_key, installation_id="987654")
   except RateLimitError as exc:
       # 429 — GitHub asked us to wait; back off by exc.retry_after_seconds.
       print(f"rate limited, retry in {exc.retry_after_seconds}s")
       ...
   except TokenMintError as exc:
       # any other token-mint failure (401, 403, 5xx, network, JWT, ...)
       ...
   ```

3. **Replace any ad-hoc 429 detection.** If you previously checked the HTTP
   status code or re-read the `Retry-After` header yourself, drop that logic and
   rely on `RateLimitError` plus `exc.retry_after_seconds` instead — the library
   already parsed the header for you (see [Handling rate limits](api.md#handling-rate-limits)).

If you do not need to distinguish rate limits from other failures, no change is
required — leave the single `except TokenMintError` handler and 429s continue to
be treated as a normal `TokenMintError` failure.
