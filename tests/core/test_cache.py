"""Tests for the in-process token cache."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from robotsix_github_auth import clear_token_cache, invalidate_token_cache
from robotsix_github_auth._cache import (
    _freeze_scopes,
    _InstallationIdCache,
    _token_cache,
)
from robotsix_github_auth._models import InstallationToken


def _make_token(offset_minutes: int = 10) -> InstallationToken:
    """Create a token that expires in *offset_minutes* from now."""
    return InstallationToken(
        token="ghs_test",
        expires_at=datetime.now(UTC) + timedelta(minutes=offset_minutes),
    )


class TestTokenCache:
    def setup_method(self) -> None:
        _token_cache.clear()

    def test_get_miss_returns_none(self) -> None:
        assert _token_cache.get("inst1") is None

    def test_put_and_get_hit(self) -> None:
        token = _make_token(10)
        _token_cache.put("inst1", None, token)
        cached = _token_cache.get("inst1")
        assert cached is token

    def test_different_scopes_different_keys(self) -> None:
        tok_a = _make_token(10)
        tok_b = _make_token(10)
        _token_cache.put("inst1", {"contents": "read"}, tok_a)
        _token_cache.put("inst1", {"contents": "write"}, tok_b)
        assert _token_cache.get("inst1", {"contents": "read"}) is tok_a
        assert _token_cache.get("inst1", {"contents": "write"}) is tok_b

    def test_scope_order_does_not_matter(self) -> None:
        token = _make_token(10)
        scopes = {"contents": "read", "issues": "write"}
        _token_cache.put("inst1", scopes, token)
        # Reversed insertion order should still hit
        assert _token_cache.get("inst1", {"issues": "write", "contents": "read"}) is token

    def test_evicts_near_expiry(self) -> None:
        # Token with only 4 minutes left (< 5 min margin)
        token = _make_token(4)
        _token_cache.put("inst1", None, token)
        assert _token_cache.get("inst1") is None

    def test_evicts_expired(self) -> None:
        token = _make_token(-5)  # expired 5 min ago
        _token_cache.put("inst1", None, token)
        assert _token_cache.get("inst1") is None

    def test_keeps_fresh_token(self) -> None:
        token = _make_token(10)
        _token_cache.put("inst1", None, token)
        assert _token_cache.get("inst1") is token

    def test_invalidate_removes_all_for_installation(self) -> None:
        tok_a = _make_token(10)
        tok_b = _make_token(10)
        _token_cache.put("inst1", {"a": "read"}, tok_a)
        _token_cache.put("inst1", {"b": "read"}, tok_b)
        _token_cache.put("inst2", None, _make_token(10))

        _token_cache.invalidate("inst1")
        assert _token_cache.get("inst1", {"a": "read"}) is None
        assert _token_cache.get("inst1", {"b": "read"}) is None
        assert _token_cache.get("inst2") is not None

    def test_invalidate_token_cache_public_api(self) -> None:
        tok_a = _make_token(10)
        tok_b = _make_token(10)
        _token_cache.put("inst1", {"a": "read"}, tok_a)
        _token_cache.put("inst1", {"b": "read"}, tok_b)
        _token_cache.put("inst2", None, _make_token(10))

        invalidate_token_cache("inst1")
        assert _token_cache.get("inst1", {"a": "read"}) is None
        assert _token_cache.get("inst1", {"b": "read"}) is None
        assert _token_cache.get("inst2") is not None

    def test_clear_token_cache_public_api(self) -> None:
        _token_cache.put("inst1", None, _make_token(10))
        _token_cache.put("inst2", None, _make_token(10))
        clear_token_cache()
        assert _token_cache.get("inst1") is None
        assert _token_cache.get("inst2") is None

    def test_clear_removes_everything(self) -> None:
        _token_cache.put("inst1", None, _make_token(10))
        _token_cache.put("inst2", None, _make_token(10))
        _token_cache.clear()
        assert _token_cache.get("inst1") is None
        assert _token_cache.get("inst2") is None

    def test_thread_safety_put_and_get(self) -> None:
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for i in range(50):
                    _token_cache.put(f"inst-{i}", None, _make_token(10))
                    _ = _token_cache.get(f"inst-{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_freeze_scopes(self) -> None:
        assert _freeze_scopes(None) == ()
        assert _freeze_scopes({"b": "read", "a": "write"}) == (
            ("a", "write"),
            ("b", "read"),
        )


class TestInstallationIdCache:
    def setup_method(self) -> None:
        self.cache = _InstallationIdCache(ttl_seconds=60.0)

    def test_get_miss_returns_none(self) -> None:
        assert self.cache.get("owner", "repo") is None

    def test_put_and_get_hit(self) -> None:
        self.cache.put("owner", "repo", "12345")
        assert self.cache.get("owner", "repo") == "12345"

    def test_distinct_owner_repo_are_distinct_keys(self) -> None:
        self.cache.put("owner-a", "repo", "111")
        self.cache.put("owner-b", "repo", "222")
        self.cache.put("owner-a", "other", "333")
        assert self.cache.get("owner-a", "repo") == "111"
        assert self.cache.get("owner-b", "repo") == "222"
        assert self.cache.get("owner-a", "other") == "333"

    def test_evicts_expired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time

        now = 1000.0
        monkeypatch.setattr(time, "monotonic", lambda: now)

        self.cache.put("owner", "repo", "12345")
        assert self.cache.get("owner", "repo") == "12345"

        # Advance past the TTL: the entry must be dropped and re-fetch returns None.
        now = 1000.0 + self.cache._ttl + 1.0
        assert self.cache.get("owner", "repo") is None

    def test_evicts_expired_removes_entry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time

        now = 1000.0
        monkeypatch.setattr(time, "monotonic", lambda: now)

        self.cache.put("owner", "repo", "12345")
        now = 1000.0 + self.cache._ttl + 1.0
        assert self.cache.get("owner", "repo") is None
        # Entry is physically removed, not merely reported expired.
        assert ("owner", "repo") not in self.cache._store

    def test_invalidate_removes_only_target_entry(self) -> None:
        self.cache.put("owner", "repo-a", "111")
        self.cache.put("owner", "repo-b", "222")
        self.cache.put("other", "repo", "333")

        self.cache.invalidate("owner", "repo-a")
        assert self.cache.get("owner", "repo-a") is None
        assert self.cache.get("owner", "repo-b") == "222"
        assert self.cache.get("other", "repo") == "333"

    def test_invalidate_missing_key_is_noop(self) -> None:
        self.cache.put("owner", "repo", "111")
        self.cache.invalidate("owner", "missing")
        assert self.cache.get("owner", "repo") == "111"

    def test_clear_removes_everything(self) -> None:
        self.cache.put("owner-a", "repo", "111")
        self.cache.put("owner-b", "repo", "222")
        self.cache.clear()
        assert self.cache.get("owner-a", "repo") is None
        assert self.cache.get("owner-b", "repo") is None

    def test_thread_safety_put_and_get(self) -> None:
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for i in range(50):
                    self.cache.put(f"owner-{i}", "repo", str(i))
                    _ = self.cache.get(f"owner-{i}", "repo")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
