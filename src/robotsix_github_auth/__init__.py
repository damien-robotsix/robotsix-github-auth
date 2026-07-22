"""robotsix-github-auth — Fleet-wide GitHub App token minting."""

from __future__ import annotations

from robotsix_github_auth._auth import mint_installation_token
from robotsix_github_auth._exceptions import GithubAuthError, ScopeError, TokenMintError
from robotsix_github_auth._models import InstallationToken
from robotsix_github_auth._scopes import validate_scopes

__all__ = [
    "GithubAuthError",
    "InstallationToken",
    "ScopeError",
    "TokenMintError",
    "mint_installation_token",
    "validate_scopes",
]
