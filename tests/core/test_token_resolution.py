"""Tests for the unified token resolution API: github_token / github_push_token."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pytest_httpx import HTTPXMock

from robotsix_github_auth import TokenMintError, github_push_token, github_token
from robotsix_github_auth._cache import _token_cache


class TestGithubTokenPatMode:
    def test_returns_explicit_pat(self) -> None:
        token = github_token(pat="ghp_explicit", auth_mode="token")
        assert token == "ghp_explicit"

    def test_reads_forge_token_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_TOKEN", "ghp_from_env")
        token = github_token(auth_mode="token")
        assert token == "ghp_from_env"

    def test_explicit_pat_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_TOKEN", "ghp_env")
        token = github_token(pat="ghp_explicit", auth_mode="token")
        assert token == "ghp_explicit"

    def test_raises_when_no_pat_provided(self) -> None:
        with pytest.raises(TokenMintError, match="No PAT provided"):
            github_token(auth_mode="token")

    def test_auth_mode_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_AUTH_MODE", "token")
        monkeypatch.setenv("FORGE_TOKEN", "ghp_from_env_mode")
        token = github_token()
        assert token == "ghp_from_env_mode"


class TestGithubTokenAppMode:
    def setup_method(self) -> None:
        _token_cache.clear()

    def test_delegates_to_mint_installation_token(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_app_token",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        token = github_token(
            app_id=app_id,
            private_key=private_key,
            installation_id="42",
            auth_mode="app",
        )
        assert token == "ghs_app_token"

    def test_app_mode_is_default(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_default_mode",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        token = github_token(
            app_id=app_id,
            private_key=private_key,
            installation_id="42",
        )
        assert token == "ghs_default_mode"

    def test_reads_app_env_vars(
        self,
        app_id: str,
        private_key: str,
        httpx_mock: HTTPXMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_APP_ID", app_id)
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", private_key)
        monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "42")
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_from_env",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        token = github_token(auth_mode="app")
        assert token == "ghs_from_env"

    def test_explicit_params_override_env(
        self,
        app_id: str,
        private_key: str,
        httpx_mock: HTTPXMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_APP_ID", "wrong_id")
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "wrong_key")
        monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "99")
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_explicit",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        token = github_token(
            app_id=app_id,
            private_key=private_key,
            installation_id="42",
            auth_mode="app",
        )
        assert token == "ghs_explicit"


class TestGithubTokenModeSelection:
    def setup_method(self) -> None:
        _token_cache.clear()

    def test_unknown_auth_mode_raises(self) -> None:
        with pytest.raises(TokenMintError, match="Unknown auth mode"):
            github_token(pat="ghp_test", auth_mode="bogus")

    def test_auth_mode_from_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_AUTH_MODE", "token")
        monkeypatch.setenv("FORGE_TOKEN", "ghp_mode_from_env")
        token = github_token()
        assert token == "ghp_mode_from_env"

    def test_app_mode_with_owner_repo(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/repos/octocat/hello-world/installation",
            json={"id": 42},
            status_code=200,
        )
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_owner_repo",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        token = github_token(
            app_id=app_id,
            private_key=private_key,
            owner="octocat",
            repo="hello-world",
            auth_mode="app",
        )
        assert token == "ghs_owner_repo"


class TestGithubPushToken:
    def setup_method(self) -> None:
        _token_cache.clear()

    def test_returns_explicit_push_token_in_pat_mode(self) -> None:
        token = github_push_token(push_token="ghp_push_explicit", auth_mode="token")
        assert token == "ghp_push_explicit"

    def test_reads_forge_push_token_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_PUSH_TOKEN", "ghp_push_env")
        token = github_push_token(auth_mode="token")
        assert token == "ghp_push_env"

    def test_falls_back_to_pat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_TOKEN", "ghp_primary")
        token = github_push_token(auth_mode="token")
        assert token == "ghp_primary"

    def test_falls_back_to_explicit_pat(self) -> None:
        token = github_push_token(pat="ghp_explicit_pat", auth_mode="token")
        assert token == "ghp_explicit_pat"

    def test_push_token_overrides_pat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORGE_TOKEN", "ghp_primary")
        monkeypatch.setenv("FORGE_PUSH_TOKEN", "ghp_push")
        token = github_push_token(auth_mode="token")
        assert token == "ghp_push"

    def test_raises_when_no_token_available(self) -> None:
        with pytest.raises(TokenMintError, match="No push token provided"):
            github_push_token(auth_mode="token")

    def test_delegates_to_app_in_app_mode(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_app_push",
                "expires_at": expires_at,
                "permissions": {"contents": "write"},
            },
            status_code=201,
        )
        token = github_push_token(
            app_id=app_id,
            private_key=private_key,
            installation_id="42",
            auth_mode="app",
        )
        assert token == "ghs_app_push"

    def test_push_token_in_pat_mode_ignores_app_params(self) -> None:
        """In PAT mode, app params should be ignored."""
        token = github_push_token(
            pat="ghp_only",
            app_id="unused",
            private_key="unused",
            installation_id="unused",
            auth_mode="token",
        )
        assert token == "ghp_only"
