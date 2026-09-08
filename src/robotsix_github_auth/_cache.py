"""In-process TTL cache for GitHub App installation tokens.

Thread-safe.  Keyed by ``(installation_id, frozen_scope_tuple)`` so that
different permission sets get separate entries.  Tokens are evicted when
their remaining lifetime drops below ``REFRESH_MARGIN_SECONDS`` (5 min).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robotsix_github_auth._models import InstallationToken

logger = logging.getLogger(__name__)

_REFRESH_MARGIN_SECONDS: float = 300.0

# TTL for cached ``owner/repo`` -> installation-id resolutions.  Kept short
# so a stale statically-configured value cannot linger, while still avoiding
# an installations-API lookup on every single mint.
_INSTALLATION_ID_TTL_SECONDS: float = 300.0


def _freeze_scopes(scopes: Mapping[str, str] | None) -> tuple[tuple[str, str], ...]:
    """Convert an optional scope mapping into a hashable, sort-stable key."""
    if scopes is None:
        return ()
    return tuple(sorted(scopes.items()))


class _TokenCache:
    """Thread-safe in-memory cache for installation tokens."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[tuple[str, tuple[tuple[str, str], ...]], InstallationToken] = {}

    def get(
        self,
        installation_id: str,
        scopes: Mapping[str, str] | None = None,
    ) -> InstallationToken | None:
        """Return a cached token if one exists and is still fresh enough."""
        key = (installation_id, _freeze_scopes(scopes))
        with self._lock:
            token = self._store.get(key)
            if token is None:
                return None
            if token.is_expired(margin_seconds=_REFRESH_MARGIN_SECONDS):
                return None
            return token

    def put(
        self,
        installation_id: str,
        scopes: Mapping[str, str] | None,
        token: InstallationToken,
    ) -> None:
        """Store a freshly minted token in the cache."""
        key = (installation_id, _freeze_scopes(scopes))
        with self._lock:
            self._store[key] = token
        logger.debug(
            "token cached installation=%s expires_at=%s",
            installation_id,
            token.expires_at.isoformat(),
        )

    def invalidate(self, installation_id: str) -> None:
        """Remove all cached tokens for the given installation."""
        with self._lock:
            keys_to_del = [k for k in self._store if k[0] == installation_id]
            for k in keys_to_del:
                del self._store[k]

    def clear(self) -> None:
        """Remove every cached entry."""
        with self._lock:
            self._store.clear()


_token_cache = _TokenCache()


class _InstallationIdCache:
    """Thread-safe TTL cache mapping ``(owner, repo)`` -> installation id.

    Each entry expires after ``ttl_seconds`` so a resolution that has
    gone stale (for example after an account-wide App reinstall) is
    re-fetched at most once per TTL window rather than on every mint.
    """

    def __init__(self, ttl_seconds: float = _INSTALLATION_ID_TTL_SECONDS) -> None:
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        # key -> (installation_id, monotonic_expiry)
        self._store: dict[tuple[str, str], tuple[str, float]] = {}

    def get(self, owner: str, repo: str) -> str | None:
        """Return a cached installation id if present and not yet expired."""
        key = (owner, repo)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            installation_id, expiry = entry
            if time.monotonic() >= expiry:
                del self._store[key]
                return None
            return installation_id

    def put(self, owner: str, repo: str, installation_id: str) -> None:
        """Cache a resolved installation id for ``owner/repo``."""
        with self._lock:
            self._store[(owner, repo)] = (installation_id, time.monotonic() + self._ttl)
        logger.debug(
            "installation id cached %s/%s installation=%s",
            owner,
            repo,
            installation_id,
        )

    def invalidate(self, owner: str, repo: str) -> None:
        """Drop any cached installation id for ``owner/repo``."""
        with self._lock:
            self._store.pop((owner, repo), None)

    def clear(self) -> None:
        """Remove every cached entry."""
        with self._lock:
            self._store.clear()


_installation_id_cache = _InstallationIdCache()
