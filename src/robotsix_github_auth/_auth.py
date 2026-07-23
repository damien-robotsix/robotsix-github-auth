"""Core GitHub App authentication: JWT signing, installation resolution, token minting."""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
from robotsix_http import RetryConfig, call_with_retry

from robotsix_github_auth._cache import _token_cache
from robotsix_github_auth._exceptions import TokenMintError
from robotsix_github_auth._models import InstallationToken

_GITHUB_API_BASE: str = "https://api.github.com"
_JWT_EXPIRY_SECONDS: int = 600
_JWT_CLOCK_SKEW: int = 60
_RETRY_CONFIG: RetryConfig = RetryConfig(max_retries=2)


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
            lambda: httpx.get(url, headers=headers),
            config=_RETRY_CONFIG,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise TokenMintError(
            f"Failed to resolve installation for {owner}/{repo}: HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise TokenMintError(f"Failed to resolve installation for {owner}/{repo}: {exc}") from exc

    data: dict[str, Any] = resp.json()
    installation_id: str | None = str(data.get("id", "")) or None
    if not installation_id:
        raise TokenMintError(f"No installation found for {owner}/{repo}")
    return installation_id


def _mint_token(
    jwt_token: str,
    installation_id: str,
    scopes: Mapping[str, str] | None = None,
    repositories: list[str] | None = None,
) -> InstallationToken:
    """POST to the GitHub API to mint an installation access token."""
    url = f"{_GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    body: dict[str, Any] = {}
    if scopes is not None:
        body["permissions"] = dict(scopes)
    if repositories is not None:
        body["repositories"] = repositories

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        resp = call_with_retry(
            lambda: httpx.post(url, headers=headers, json=body),
            config=_RETRY_CONFIG,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise TokenMintError(
            f"Failed to mint token for installation {installation_id}: "
            f"HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise TokenMintError(
            f"Failed to mint token for installation {installation_id}: {exc}"
        ) from exc

    data: dict[str, Any] = resp.json()
    expires_at_str: str = data["expires_at"]
    expires_at = datetime.fromisoformat(expires_at_str).replace(tzinfo=UTC)
    return InstallationToken(
        token=data["token"],
        expires_at=expires_at,
        permissions=data.get("permissions", {}),
    )


def mint_installation_token(
    app_id: str,
    private_key: str,
    installation_id: str | None = None,
    *,
    owner: str | None = None,
    repo: str | None = None,
    scopes: Mapping[str, str] | None = None,
    ttl_seconds: int = 3600,
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
        ttl_seconds: Requested token lifetime in seconds (not
            guaranteed — GitHub caps tokens at 1 hour).

    Returns:
        A freshly minted (or cached) ``InstallationToken``.

    Raises:
        TokenMintError: When the token cannot be minted.
    """
    if installation_id is None and not (owner and repo):
        raise TokenMintError("Either installation_id or both owner and repo must be provided.")

    # Try the cache when we know the installation_id
    if installation_id is not None:
        cached = _token_cache.get(installation_id, scopes)
        if cached is not None:
            return cached

    jwt_token = _build_app_jwt(app_id, private_key)

    if installation_id is not None:
        resolved_id = installation_id
    else:
        assert owner is not None and repo is not None
        resolved_id = _resolve_installation_id(jwt_token, owner, repo)

    token = _mint_token(jwt_token, resolved_id, scopes)

    _token_cache.put(resolved_id, scopes, token)
    return token
