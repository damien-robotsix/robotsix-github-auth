# Security Policy

## Supported Versions

The latest release of `robotsix-github-auth` receives security fixes.

## Reporting a Vulnerability

Please report security vulnerabilities via GitHub Security Advisories
(Security tab → Advisories → Report a vulnerability). Do NOT file a
public issue.

We aim to acknowledge reports within 48 hours and publish fixes within
7 days of confirmation.

## Scope

In scope:

- GitHub App token minting and caching (`src/robotsix_github_auth/_auth.py`,
  `src/robotsix_github_auth/_cache.py`).
- Token resolution, including installation and permission scope handling.
- Leakage of secrets (App private keys, JWTs, installation tokens) through
  logs, exception messages, or reprs.

Out of scope:

- Vulnerabilities in the GitHub API itself, or in third-party dependencies
  such as PyGithub or httpx. Please report those upstream.
- Operator misconfiguration, for example a leaked App private key that was
  stored insecurely by the deployer.

## What to Include

- Affected version (`robotsix-github-auth` release version or commit SHA).
- Steps to reproduce, ideally a minimal script or test case.
- Impact on tokens or installations (what an attacker could obtain or do).
