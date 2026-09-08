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

    Surfaced when a token mint returns HTTP 404 — typically because the
    cached installation id is stale (the App was reinstalled and the id
    changed) and re-resolving the id still yields a 404.

    Inherits from :class:`TokenMintError` so existing callers that catch
    ``TokenMintError`` keep working.

    Attributes:
        owner: Repository owner, when known.
        repo: Repository name, when known.
    """

    def __init__(self, message: str, owner: str | None = None, repo: str | None = None) -> None:
        super().__init__(message)
        self.owner: str | None = owner
        self.repo: str | None = repo


class ScopeError(GithubAuthError):
    """Raised when token permissions are insufficient for the requested operation."""

    def __init__(self, message: str, missing: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing: list[str] = missing or []
