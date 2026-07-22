## 0.0.0 (unreleased)

- Initial release: fleet-wide GitHub App installation-token minting library.
  - `mint_installation_token()` — build App JWT (RS256), resolve installation ID from owner/repo, mint tokens via GitHub REST API, with optional permission narrowing.
  - `InstallationToken` dataclass with `token`, `expires_at`, `permissions`, `seconds_remaining`, and `is_expired`.
  - Thread-safe in-process cache keyed by `(installation_id, scope-set)` with 5-minute refresh margin.
  - `validate_scopes()` helper with hierarchical permission checking (`admin` > `write` > `read`).
  - Typed exceptions: `GithubAuthError`, `TokenMintError`, `ScopeError`.
  - Full unit test suite (38 tests) with mocked HTTP.
