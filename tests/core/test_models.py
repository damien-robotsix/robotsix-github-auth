"""Tests for InstallationToken data model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from robotsix_github_auth import InstallationToken


class TestInstallationToken:
    def test_creation_defaults(self) -> None:
        tok = InstallationToken(
            token="ghs_abc123",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert tok.token == "ghs_abc123"
        assert tok.permissions == {}

    def test_creation_with_permissions(self) -> None:
        tok = InstallationToken(
            token="ghs_abc123",
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
            permissions={"contents": "read", "issues": "write"},
        )
        assert tok.permissions == {"contents": "read", "issues": "write"}

    def test_seconds_remaining_positive(self) -> None:
        future = datetime.now(UTC) + timedelta(minutes=10)
        tok = InstallationToken(token="ghs_abc123", expires_at=future)
        assert tok.seconds_remaining > 0
        assert tok.seconds_remaining <= 600

    def test_seconds_remaining_negative(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=10)
        tok = InstallationToken(token="ghs_abc123", expires_at=past)
        assert tok.seconds_remaining < 0

    def test_is_expired_false(self) -> None:
        future = datetime.now(UTC) + timedelta(minutes=10)
        tok = InstallationToken(token="ghs_abc123", expires_at=future)
        assert tok.is_expired() is False

    def test_is_expired_true(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=10)
        tok = InstallationToken(token="ghs_abc123", expires_at=past)
        assert tok.is_expired() is True

    def test_is_expired_with_margin(self) -> None:
        future = datetime.now(UTC) + timedelta(minutes=3)
        tok = InstallationToken(token="ghs_abc123", expires_at=future)
        # Not expired without margin
        assert tok.is_expired() is False
        # Expired within a 5-minute margin
        assert tok.is_expired(margin_seconds=300) is True
