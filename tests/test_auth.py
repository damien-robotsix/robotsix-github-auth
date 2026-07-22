"""Tests for the core auth module: JWT building, installation resolution, token minting."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from pytest_httpx import HTTPXMock

from robotsix_github_auth import TokenMintError, mint_installation_token
from robotsix_github_auth._auth import _build_app_jwt, _resolve_installation_id
from robotsix_github_auth._cache import _token_cache


def _load_public_key(private_key_pem: str) -> str:
    """Derive the public key from a private key PEM."""
    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    public_key = private_key.public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


class TestBuildAppJwt:
    def test_jwt_structure(self, app_id: str, private_key: str) -> None:
        token = _build_app_jwt(app_id, private_key)
        public_key = _load_public_key(private_key)
        decoded = jwt.decode(token, public_key, algorithms=["RS256"])
        assert decoded["iss"] == app_id
        assert "iat" in decoded
        assert "exp" in decoded
        assert decoded["exp"] > decoded["iat"]

    def test_jwt_algorithm_is_rs256(self, app_id: str, private_key: str) -> None:
        token = _build_app_jwt(app_id, private_key)
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_jwt_signing_failure(self) -> None:
        with pytest.raises(TokenMintError, match="Failed to sign App JWT"):
            _build_app_jwt("123", "not-a-valid-key")


class TestResolveInstallationId:
    def test_resolves_from_repo(self, app_id: str, private_key: str, httpx_mock: HTTPXMock) -> None:
        jwt_token = _build_app_jwt(app_id, private_key)
        httpx_mock.add_response(
            url="https://api.github.com/repos/octocat/hello-world/installation",
            json={"id": 42, "account": {"login": "octocat"}},
            status_code=200,
        )
        import httpx

        with httpx.Client() as client:
            iid = _resolve_installation_id(client, jwt_token, "octocat", "hello-world")
        assert iid == "42"

    def test_raises_on_404(self, app_id: str, private_key: str, httpx_mock: HTTPXMock) -> None:
        jwt_token = _build_app_jwt(app_id, private_key)
        httpx_mock.add_response(
            url="https://api.github.com/repos/octocat/hello-world/installation",
            status_code=404,
        )
        import httpx

        with httpx.Client() as client, pytest.raises(TokenMintError, match="HTTP 404"):
            _resolve_installation_id(client, jwt_token, "octocat", "hello-world")


class TestMintInstallationToken:
    def setup_method(self) -> None:
        _token_cache.clear()

    @staticmethod
    def _mock_installation_api(
        httpx_mock: HTTPXMock,
        *,
        installation_id: int = 42,
        token: str = "ghs_mocktoken123",
        expires_at: str | None = None,
        permissions: dict | None = None,
    ) -> None:
        """Set up the mock HTTP responses for a full mint flow."""
        if expires_at is None:
            expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        if permissions is None:
            permissions = {"contents": "read"}

        # Installation resolution endpoint
        httpx_mock.add_response(
            url="https://api.github.com/repos/octocat/hello-world/installation",
            json={"id": installation_id},
            status_code=200,
        )
        # Token minting endpoint
        httpx_mock.add_response(
            url=f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            json={
                "token": token,
                "expires_at": expires_at,
                "permissions": permissions,
            },
            status_code=201,
        )

    def test_mints_with_installation_id(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_abc",
                "expires_at": expires_at,
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        token = mint_installation_token(app_id, private_key, installation_id="42")
        assert token.token == "ghs_abc"
        assert token.permissions == {"contents": "read"}

    def test_mints_with_owner_repo_resolution(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        self._mock_installation_api(httpx_mock)
        token = mint_installation_token(
            app_id,
            private_key,
            owner="octocat",
            repo="hello-world",
        )
        assert token.token == "ghs_mocktoken123"

    def test_raises_when_missing_params(self, app_id: str, private_key: str) -> None:
        with pytest.raises(TokenMintError, match="installation_id or both owner and repo"):
            mint_installation_token(app_id, private_key)

    def test_raises_when_only_owner_given(self, app_id: str, private_key: str) -> None:
        with pytest.raises(TokenMintError, match="installation_id or both owner and repo"):
            mint_installation_token(app_id, private_key, owner="octocat")

    def test_raises_when_only_repo_given(self, app_id: str, private_key: str) -> None:
        with pytest.raises(TokenMintError, match="installation_id or both owner and repo"):
            mint_installation_token(app_id, private_key, repo="hello-world")

    def test_caches_and_reuses_token(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_first",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        # First call: mint
        token1 = mint_installation_token(app_id, private_key, installation_id="42")
        assert token1.token == "ghs_first"

        # Second call: should come from cache (no additional HTTP mock needed)
        # We need to NOT add another response — if the cache works, no request is made.
        # However, httpx_mock will raise if an unexpected request occurs.
        token2 = mint_installation_token(app_id, private_key, installation_id="42")
        assert token2.token == "ghs_first"
        assert token2 is token1  # Same object from cache

    def test_different_scopes_different_cache_entries(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        # First scope set
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_read",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "permissions": {"contents": "read"},
            },
            status_code=201,
        )
        tok_read = mint_installation_token(
            app_id,
            private_key,
            installation_id="42",
            scopes={"contents": "read"},
        )
        assert tok_read.token == "ghs_read"

        # Second scope set (different)
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_write",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "permissions": {"contents": "write"},
            },
            status_code=201,
        )
        tok_write = mint_installation_token(
            app_id,
            private_key,
            installation_id="42",
            scopes={"contents": "write"},
        )
        assert tok_write.token == "ghs_write"

    def test_http_error_propagates(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            status_code=500,
        )
        with pytest.raises(TokenMintError, match="HTTP 500"):
            mint_installation_token(app_id, private_key, installation_id="42")

    def test_passes_scopes_in_request(
        self, app_id: str, private_key: str, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url="https://api.github.com/app/installations/42/access_tokens",
            json={
                "token": "ghs_scoped",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "permissions": {"contents": "read", "issues": "write"},
            },
            status_code=201,
        )
        token = mint_installation_token(
            app_id,
            private_key,
            installation_id="42",
            scopes={"contents": "read", "issues": "write"},
        )
        assert token.token == "ghs_scoped"

        # Verify the request body was sent correctly
        request = httpx_mock.get_request()
        body = json.loads(request.content)
        assert "permissions" in body
        assert body["permissions"] == {"contents": "read", "issues": "write"}
