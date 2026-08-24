"""Tests for diagnostic logging: ensure DEBUG records are emitted and no secrets leak."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from pytest_httpx import HTTPXMock

from robotsix_github_auth import mint_installation_token
from robotsix_github_auth._cache import _token_cache


class TestDiagnosticLogging:
    def setup_method(self) -> None:
        _token_cache.clear()

    def test_mint_emits_debug_record(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A mint operation emits at least one DEBUG record with the installation id."""
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_test123",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )

        with caplog.at_level(logging.DEBUG, logger="robotsix_github_auth"):
            mint_installation_token(app_id, private_key, installation_id="42")

        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_records) >= 1, "Expected at least one DEBUG record on mint"

        # At least one record should mention the installation id
        messages = [r.message for r in debug_records]
        assert (
            any("42" in msg for msg in messages)
        ), f"No DEBUG record mentions installation 42: {messages}"

        # No token value may appear in any emitted record
        all_messages = " ".join(messages)
        assert "ghs_test123" not in all_messages, "Token string leaked into logs!"

    def test_cache_hit_emits_debug_record(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A cache hit emits a DEBUG record indicating the hit."""
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_cached",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )

        with caplog.at_level(logging.DEBUG, logger="robotsix_github_auth"):
            mint_installation_token(app_id, private_key, installation_id="42")
        assert any(
            "cache miss" in r.message for r in caplog.records if r.levelno == logging.DEBUG
        ), "Expected a cache-miss record on first mint"

        # Second call: should be a cache hit — no extra mock response needed
        with caplog.at_level(logging.DEBUG, logger="robotsix_github_auth"):
            mint_installation_token(app_id, private_key, installation_id="42")

        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        messages = [r.message for r in debug_records]
        assert any(
            "cache hit" in msg for msg in messages
        ), f"Expected a cache-hit DEBUG record, got: {messages}"

        # No token value may appear in any emitted record (including cache-hit)
        all_messages = " ".join(messages)
        assert "ghs_cached" not in all_messages, "Token string leaked into cache-hit log!"
