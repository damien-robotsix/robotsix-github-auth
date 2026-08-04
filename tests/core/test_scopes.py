"""Tests for scope validation."""

from __future__ import annotations

import pytest

from robotsix_github_auth import ScopeError, validate_scopes


class TestValidateScopes:
    def test_passes_when_all_required_present(self) -> None:
        validate_scopes(
            {"contents": "write", "issues": "read"},
            {"contents": "read", "issues": "read"},
        )

    def test_passes_when_write_satisfies_read(self) -> None:
        validate_scopes({"contents": "write"}, {"contents": "read"})

    def test_passes_when_admin_satisfies_write(self) -> None:
        validate_scopes({"contents": "admin"}, {"contents": "write"})

    def test_raises_when_permission_missing(self) -> None:
        with pytest.raises(ScopeError, match="issues"):
            validate_scopes({"contents": "read"}, {"issues": "write"})

    def test_raises_when_level_too_low(self) -> None:
        with pytest.raises(ScopeError, match="contents"):
            validate_scopes({"contents": "read"}, {"contents": "write"})

    def test_noop_when_required_empty(self) -> None:
        validate_scopes({"contents": "admin"}, {})

    def test_raises_with_multiple_missing(self) -> None:
        with pytest.raises(ScopeError) as exc_info:
            validate_scopes(
                {"contents": "read"},
                {"contents": "write", "issues": "read"},
            )
        assert "contents" in str(exc_info.value)
        assert "issues" in str(exc_info.value)
        assert len(exc_info.value.missing) == 2

    def test_raises_when_required_has_unknown_level(self) -> None:
        with pytest.raises(ValueError, match="superadmin"):
            validate_scopes({"contents": "read"}, {"contents": "superadmin"})

    def test_raises_when_token_has_unknown_level(self) -> None:
        with pytest.raises(ScopeError, match="superadmin"):
            validate_scopes({"contents": "superadmin"}, {"contents": "read"})
