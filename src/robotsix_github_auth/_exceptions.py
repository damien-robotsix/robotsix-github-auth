"""Typed exceptions for the robotsix-github-auth library."""

from __future__ import annotations


class GithubAuthError(Exception):
    """Base exception for all GitHub Auth errors."""


class TokenMintError(GithubAuthError):
    """Raised when a token cannot be minted.

    This covers HTTP failures, JWT signing errors, and missing parameters.
    """


class RateLimitError(TokenMintError):
    """Raised when a 429 rate limit response is received.

    Inherits from :class:`TokenMintError` for backward compatibility so
    existing callers that catch ``TokenMintError`` continue to work.

    Attributes:
        retry_after_seconds: Number of seconds to wait before retrying (parsed from
            Retry-After header, defaulting to 60 if unparseable).
    """

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds: int = retry_after_seconds or 60


class RepoNotInstalledError(TokenMintError):
    """Raised when the GitHub App is not installed on the target repository.

    Surfaced instead of an opaque HTTP 404 from the installation-lookup
    endpoint so callers get a clear, actionable message.  A stale/static
    installation id (for example after an account-wide App reinstall) is
    a common cause, which is why the token-mint path resolves the
    installation id per owner/repo instead of trusting a static value.

    Inherits from :class:`TokenMintError` so existing callers that catch
    ``TokenMintError`` continue to work.

    Attributes:
        owner: Repository owner (org or user).
        repo: Repository name.
    """

    def __init__(self, owner: str, repo: str, message: str | None = None) -> None:
        self.owner: str = owner
        self.repo: str = repo
        super().__init__(
            message
            or (
                f"GitHub App is not installed on {owner}/{repo}. Install the App on "
                f"this repository (its installation id may have changed after an "
                f"account-wide reinstall)."
            )
        )


class ScopeError(GithubAuthError):
    """Raised when token permissions are insufficient for the requested operation."""

    def __init__(self, message: str, missing: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing: list[str] = missing or []
