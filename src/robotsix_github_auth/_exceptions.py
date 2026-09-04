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


class ScopeError(GithubAuthError):
    """Raised when token permissions are insufficient for the requested operation."""

    def __init__(self, message: str, missing: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing: list[str] = missing or []
