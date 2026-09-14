"""Core GitHub authentication: PAT mode, JWT signing, installation resolution, token minting."""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
import jwt
from robotsix_http import RetryConfig, call_with_retry

from robotsix_github_auth._cache import (
    _freeze_scopes,
    _installation_id_cache,
    _token_cache,
)
from robotsix_github_auth._exceptions import (
    RateLimitError,
    RepoNotInstalledError,
    TokenMintError,
)
from robotsix_github_auth._models import InstallationToken

logger = logging.getLogger(__name__)

# --- Environment variable names for auth-mode configuration ---
_GITHUB_AUTH_MODE_ENV: str = "GITHUB_AUTH_MODE"
_FORGE_TOKEN_ENV: str = "FORGE_TOKEN"  # noqa: S105
_FORGE_PUSH_TOKEN_ENV: str = "FORGE_PUSH_TOKEN"  # noqa: S105
_GITHUB_APP_ID_ENV: str = "GITHUB_APP_ID"
_GITHUB_APP_PRIVATE_KEY_ENV: str = "GITHUB_APP_PRIVATE_KEY"
_GITHUB_APP_INSTALLATION_ID_ENV: str = "GITHUB_APP_INSTALLATION_ID"

_GITHUB_API_BASE: str = "https://api.github.com"
_JWT_EXPIRY_SECONDS: int = 600
_JWT_CLOCK_SKEW: int = 60
_RETRY_CONFIG: RetryConfig = RetryConfig(max_retries=2)

_AUTH_TIMEOUT: float = 10.0
_GITHUB_CLIENT = httpx.Client(timeout=httpx.Timeout(_AUTH_TIMEOUT))

# Per-key locks for single-flight mint coalescing.
# Keyed by the same (installation_id, frozen_scope_tuple) as _TokenCache
# so that concurrent callers for distinct installations/scopes do not
# block each other.
_MintKey = tuple[str, tuple[tuple[str, str], ...]]
_mint_locks: dict[_MintKey, threading.Lock] = {}
_mint_locks_lock = threading.Lock()


def _acquire_mint_lock(key: _MintKey) -> threading.Lock:
    """Get or create the per-key lock, then acquire it.

    Returns the acquired lock so the caller can use it as a context
    manager::

        lock = _acquire_mint_lock(key)
        try:
            ...
        finally:
            lock.release()
    """
    with _mint_locks_lock:
        lock = _mint_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _mint_locks[key] = lock
    lock.acquire()
    return lock


def _build_app_jwt(app_id: str, private_key: str) -> str:
    """Build a short-lived RS256 JWT for authenticating as a GitHub App."""
    now = int(time.time()) - _JWT_CLOCK_SKEW
    payload = {
        "iat": now,
        "exp": now + _JWT_EXPIRY_SECONDS,
        "iss": app_id,
    }
    try:
        return jwt.encode(payload, private_key, algorithm="RS256")
    except Exception as exc:
        raise TokenMintError(f"Failed to sign App JWT: {exc}") from exc


def _parse_retry_after(header_value: str | None) -> int:
    """Parse the ``Retry-After`` header (seconds as int or HTTP-date string).

    Defaults to 60 seconds when the header is missing or unparseable.
    """
    if not header_value:
        return 60
    try:
        return int(header_value)  # Try as seconds
    except ValueError:
        # Try as HTTP-date; fall back to 60.
        try:
            dt = parsedate_to_datetime(header_value)
            delta = dt - datetime.now(UTC)
            return max(1, int(delta.total_seconds()))
        except Exception:
            return 60


class _MintNotFoundError(TokenMintError):
    """Internal: a mint request returned HTTP 404.

    Signals that the installation id used for the mint is no longer
    valid (for example the installation was recreated after an
    account-wide App reinstall), so the caller can invalidate the
    resolved-id cache and re-resolve once before failing.
    """


def _resolve_installation_id(
    jwt_token: str,
    owner: str,
    repo: str,
) -> str:
    """Resolve the installation ID for a repository via the GitHub API."""
    url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/installation"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        resp = call_with_retry(
            lambda: _GITHUB_CLIENT.get(url, headers=headers),
            config=_RETRY_CONFIG,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            retry_after = _parse_retry_after(exc.response.headers.get("Retry-After"))
            raise RateLimitError(
                f"Rate limited by GitHub API: {exc.response.status_code}",
                retry_after_seconds=retry_after,
            ) from exc
        if exc.response.status_code == 404:
            raise RepoNotInstalledError(owner, repo) from exc
        raise TokenMintError(
            f"Failed to resolve installation for {owner}/{repo}: HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise TokenMintError(f"Failed to resolve installation for {owner}/{repo}: {exc}") from exc
    except Exception as exc:
        raise TokenMintError(f"Failed to resolve installation for {owner}/{repo}: {exc}") from exc

    installation_id: str | None = str(data.get("id", "")) or None
    if not installation_id:
        raise RepoNotInstalledError(owner, repo)
    logger.debug("resolved installation=%s for %s/%s", installation_id, owner, repo)
    return installation_id


def _resolve_installation_id_for_repo(jwt_token: str, repo_full_name: str) -> str:
    """Resolve the *current* installation id covering ``owner/repo``.

    ``repo_full_name`` is an ``"owner/repo"`` string.  The short-TTL
    installation-id cache is consulted first; on a miss the GitHub App
    installations API is queried (App-JWT authenticated) and the result
    is cached.  Resolving per repo — rather than trusting a statically
    configured installation id — is what prevents a stale id from
    breaking token minting after an account-wide App reinstall.
    """
    owner, sep, repo = repo_full_name.partition("/")
    if not owner or not sep or not repo:
        raise TokenMintError(f"Invalid repository '{repo_full_name}'; expected 'owner/repo'.")
    cached = _installation_id_cache.get(owner, repo)
    if cached is not None:
        logger.debug("installation id cache hit %s/%s installation=%s", owner, repo, cached)
        return cached
    installation_id = _resolve_installation_id(jwt_token, owner, repo)
    _installation_id_cache.put(owner, repo, installation_id)
    return installation_id


def resolve_installation_id_for_repo(
    *,
    owner: str,
    repo: str,
    app_id: str,
    private_key: str,
) -> str:
    """Resolve and cache the GitHub App installation id covering ``owner/repo``.

    Public per-repo installation resolution with built-in short-TTL
    caching.  Builds a short-lived App JWT and resolves the current
    installation id covering the repository via the GitHub installations
    API, caching it in-process so repeated calls for the same repo do not
    re-hit the API.  Resolving per repo — rather than trusting a statically
    configured installation id — is what prevents a stale id from breaking
    token minting after an account-wide App reinstall.
    """
    jwt_token = _build_app_jwt(app_id, private_key)
    return _resolve_installation_id_for_repo(jwt_token, f"{owner}/{repo}")


def _mint_token(
    jwt_token: str,
    installation_id: str,
    scopes: Mapping[str, str] | None = None,
) -> InstallationToken:
    """POST to the GitHub API to mint an installation access token."""
    url = f"{_GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    body: dict[str, Any] = {}
    if scopes is not None:
        body["permissions"] = dict(scopes)

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    logger.debug(
        "minting installation token for installation=%s scopes=%s",
        installation_id,
        sorted((scopes or {}).keys()),
    )
    try:
        resp = call_with_retry(
            lambda: _GITHUB_CLIENT.post(url, headers=headers, json=body),
            config=_RETRY_CONFIG,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            retry_after = _parse_retry_after(exc.response.headers.get("Retry-After"))
            raise RateLimitError(
                f"Rate limited by GitHub API: {exc.response.status_code}",
                retry_after_seconds=retry_after,
            ) from exc
        if exc.response.status_code == 404:
            # The installation id is no longer valid (e.g. it was recreated
            # after an account-wide App reinstall).  Signalled distinctly so
            # the caller can invalidate the resolved-id cache and re-resolve.
            raise _MintNotFoundError(
                f"Failed to mint token for installation {installation_id}: HTTP 404"
            ) from exc
        raise TokenMintError(
            f"Failed to mint token for installation {installation_id}: "
            f"HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise TokenMintError(
            f"Failed to mint token for installation {installation_id}: {exc}"
        ) from exc
    except Exception as exc:
        raise TokenMintError(
            f"Failed to mint token for installation {installation_id}: {exc}"
        ) from exc

    try:
        expires_at_str: str = data["expires_at"]
        expires_at = datetime.fromisoformat(expires_at_str).astimezone(UTC)
        token_str: str = data["token"]
    except (KeyError, ValueError) as exc:
        raise TokenMintError(
            f"Malformed token response for installation {installation_id}: "
            f"missing or invalid field ({exc})"
        ) from exc
    inst_token = InstallationToken(
        token=token_str,
        expires_at=expires_at,
        permissions=data.get("permissions", {}),
    )
    logger.debug(
        "minted installation token for installation=%s expires_at=%s",
        installation_id,
        expires_at.isoformat(),
    )
    return inst_token


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
) -> str:
    """Resolve a GitHub token using PAT or GitHub App authentication.

    When *auth_mode* is ``"token"`` (or the ``GITHUB_AUTH_MODE`` env var
    is set to ``"token"``), the token is read from *pat* (or the
    ``FORGE_TOKEN`` environment variable).

    When *auth_mode* is ``"app"`` (the default), the token is minted via
    :func:`_resolve_token` and its raw token string is returned.

    Args:
        pat: Personal access token (PAT mode).  Falls back to
            ``FORGE_TOKEN`` environment variable.
        app_id: GitHub App ID (App mode).  Falls back to
            ``GITHUB_APP_ID`` environment variable.
        private_key: App private key PEM (App mode).  Falls back to
            ``GITHUB_APP_PRIVATE_KEY`` environment variable.
        installation_id: App installation ID (App mode).  Falls back to
            ``GITHUB_APP_INSTALLATION_ID`` environment variable.
        owner: Repository owner for installation resolution (App mode).
        repo: Repository name for installation resolution (App mode).
        scopes: Permission narrowing for the installation token (App mode).
        auth_mode: ``"token"`` or ``"app"``.  Defaults to
            ``os.environ.get("GITHUB_AUTH_MODE", "app")``.

    Returns:
        A GitHub bearer token string.

    Raises:
        TokenMintError: When no token can be resolved.
    """
    resolved_mode = auth_mode or os.environ.get(_GITHUB_AUTH_MODE_ENV, "app")

    if resolved_mode == "token":
        token = pat or os.environ.get(_FORGE_TOKEN_ENV)
        if not token:
            raise TokenMintError(f"No PAT provided. Set {_FORGE_TOKEN_ENV} or pass ``pat=``.")
        return token

    if resolved_mode == "app":
        inst_token = _resolve_token(
            app_id or os.environ.get(_GITHUB_APP_ID_ENV, ""),
            private_key or os.environ.get(_GITHUB_APP_PRIVATE_KEY_ENV, ""),
            owner,
            repo,
            scopes,
            install_id=installation_id or os.environ.get(_GITHUB_APP_INSTALLATION_ID_ENV) or None,
        )
        return inst_token.token

    raise TokenMintError(
        f"Unknown auth mode '{resolved_mode}'. Set {_GITHUB_AUTH_MODE_ENV} to 'token' or 'app'."
    )


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
) -> str:
    """Resolve a GitHub push token.

    In PAT mode, returns *push_token* (or ``FORGE_PUSH_TOKEN`` env var),
    falling back to the primary PAT (from *pat* or ``FORGE_TOKEN``).

    In App mode, delegates to :func:`github_token`.

    Args:
        pat: Primary personal access token, used as fallback when
            *push_token* is not set (PAT mode).
        push_token: Push-specific PAT (PAT mode).  Falls back to
            ``FORGE_PUSH_TOKEN`` environment variable.
        app_id: GitHub App ID (App mode).
        private_key: App private key PEM (App mode).
        installation_id: App installation ID (App mode).
        owner: Repository owner for installation resolution (App mode).
        repo: Repository name for installation resolution (App mode).
        scopes: Permission narrowing for the installation token (App mode).
        auth_mode: ``"token"`` or ``"app"``.  Defaults to
            ``os.environ.get("GITHUB_AUTH_MODE", "app")``.

    Returns:
        A GitHub bearer token string suitable for push operations.

    Raises:
        TokenMintError: When no token can be resolved.
    """
    resolved_mode = auth_mode or os.environ.get(_GITHUB_AUTH_MODE_ENV, "app")

    if resolved_mode == "token":
        token = push_token or os.environ.get(_FORGE_PUSH_TOKEN_ENV)
        if not token:
            token = pat or os.environ.get(_FORGE_TOKEN_ENV)
        if not token:
            raise TokenMintError(
                f"No push token provided. Set {_FORGE_PUSH_TOKEN_ENV} or {_FORGE_TOKEN_ENV}."
            )
        return token

    # App mode: same as github_token (no separate push token concept for Apps)
    return github_token(
        pat=pat,
        app_id=app_id,
        private_key=private_key,
        installation_id=installation_id,
        owner=owner,
        repo=repo,
        scopes=scopes,
        auth_mode=resolved_mode,
    )


def _close_github_client() -> None:
    """Close the shared GitHub API HTTP client."""
    _GITHUB_CLIENT.close()


atexit.register(_close_github_client)


def _mint_with_cache(
    jwt_token: str,
    resolved_id: str,
    scopes: Mapping[str, str] | None,
) -> InstallationToken:
    """Return a cached token for ``resolved_id`` or single-flight the mint."""
    cached = _token_cache.get(resolved_id, scopes)
    if cached is not None:
        logger.debug("token cache hit installation=%s", resolved_id)
        return cached

    key: _MintKey = (resolved_id, _freeze_scopes(scopes))
    mint_lock = _acquire_mint_lock(key)
    try:
        # Double-checked locking: another thread may have populated
        # the cache while we waited for the per-key lock.
        cached = _token_cache.get(resolved_id, scopes)
        if cached is not None:
            logger.debug("token cache hit (after lock) installation=%s", resolved_id)
            return cached
        logger.debug("cache miss, minting installation=%s", resolved_id)
        token = _mint_token(jwt_token, resolved_id, scopes)
        _token_cache.put(resolved_id, scopes, token)
        return token
    finally:
        mint_lock.release()


def _resolve_token(
    app_id: str,
    private_key: str,
    owner: str | None,
    repo: str | None,
    scopes: Mapping[str, str] | None,
    *,
    install_id: str | None = None,
) -> InstallationToken:
    """Mint (or fetch from cache) a GitHub App installation token.

    Encapsulates the shared App-mode mint flow: build a JWT, resolve the
    installation ID from ``owner``/``repo`` when possible, check the
    in-process token cache, and single-flight the mint under a per-key
    lock.

    When ``owner``/``repo`` are known the installation id is resolved
    per repo (via a short-TTL cache) so a stale/static installation id
    cannot cause a 404 after an account-wide App reinstall.  The
    configured ``install_id`` is used only as a last-resort fallback when
    the App-JWT installations lookup is unavailable.  A 404 during mint
    invalidates the resolved-id cache and triggers a single re-resolve
    before failing with :class:`RepoNotInstalledError`.
    """
    if install_id is None and not (owner and repo):
        raise TokenMintError("Either installation_id or both owner and repo must be provided.")

    jwt_token = _build_app_jwt(app_id, private_key)

    # Static-only path: no owner/repo to resolve against.
    if not (owner and repo):
        if install_id is None:  # pragma: no cover - guarded by the check above
            raise TokenMintError("owner and repo must be provided when installation_id is omitted")
        return _mint_with_cache(jwt_token, install_id, scopes)

    # owner/repo path: auto-resolve the current installation id.
    repo_full_name = f"{owner}/{repo}"
    resolved_from_repo = True
    try:
        resolved_id = _resolve_installation_id_for_repo(jwt_token, repo_full_name)
    except RepoNotInstalledError, RateLimitError:
        raise
    except TokenMintError:
        # The App-JWT installations lookup is unavailable (network error,
        # 5xx, ...).  Fall back to the statically-configured installation
        # id as a last resort, if one was provided.
        if install_id is None:
            raise
        logger.warning(
            "installation-id resolution for %s failed; falling back to configured installation id",
            repo_full_name,
        )
        resolved_id = install_id
        resolved_from_repo = False

    try:
        return _mint_with_cache(jwt_token, resolved_id, scopes)
    except _MintNotFoundError as exc:
        if not resolved_from_repo:
            # The configured fallback id is stale and there is nothing
            # fresher to try.
            raise RepoNotInstalledError(owner, repo) from exc
        # The resolved id went stale between resolution and mint (e.g. an
        # account-wide reinstall).  Invalidate and re-resolve exactly once.
        logger.info("mint returned 404 for %s; re-resolving installation id", repo_full_name)
        _installation_id_cache.invalidate(owner, repo)
        resolved_id = _resolve_installation_id_for_repo(jwt_token, repo_full_name)
        try:
            return _mint_with_cache(jwt_token, resolved_id, scopes)
        except _MintNotFoundError as exc2:
            raise RepoNotInstalledError(owner, repo) from exc2


def mint_installation_token(
    app_id: str,
    private_key: str,
    installation_id: str | None = None,
    *,
    owner: str | None = None,
    repo: str | None = None,
    scopes: Mapping[str, str] | None = None,
) -> InstallationToken:
    """Mint a GitHub App installation access token.

    Args:
        app_id: The GitHub App ID.
        private_key: The App's PEM-encoded RSA private key.
        installation_id: The installation ID to mint a token for.
            If omitted, ``owner`` and ``repo`` must be provided so the
            installation can be resolved automatically.
        owner: Repository owner (org or user).  Required when
            ``installation_id`` is not given.
        repo: Repository name.  Required when ``installation_id`` is
            not given.
        scopes: Optional permission narrowing.  Keys are permission
            names; values are ``"read"``, ``"write"``, or ``"admin"``.

    Returns:
        A freshly minted (or cached) ``InstallationToken``.

    Raises:
        TokenMintError: When the token cannot be minted.
    """
    return _resolve_token(
        app_id,
        private_key,
        owner,
        repo,
        scopes,
        install_id=installation_id,
    )
