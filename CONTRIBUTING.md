# Contributing to robotsix-github-auth

Thank you for your interest in contributing! This guide explains how to
set up a development environment, run the checks that CI enforces, and
submit changes that are easy to review and merge.

By participating in this project you agree to uphold a respectful,
collaborative environment for everyone involved.

## Getting Started

This project uses [uv](https://docs.astral.sh/uv/) to manage the Python
environment and dependencies. The project targets **Python >= 3.14**.

Install the development environment and dependencies:

```bash
uv sync --dev
```

`uv sync --dev` creates (or updates) a virtual environment from the
locked `uv.lock` file and installs the project together with its `dev`
dependency group. Prefix the development tools below with `uv run` so
they execute inside that environment.

The tools used in this project are:

- **uv** — resolves, locks, and installs dependencies, and runs commands
  inside the managed virtual environment.
- **pytest** — runs the test suite.
- **ruff** — lints and formats the code.
- **mypy** — performs static type checking in strict mode.
- **deptry** — checks for missing, unused, or misplaced dependencies.

### Troubleshooting setup

- **`No module named ...` when running a tool** — you are running the
  tool outside the managed environment. Prefix it with `uv run`.
- **Dependencies look stale or out of date** — re-run `uv sync --dev`;
  it reconciles the environment with `uv.lock`.
- **Lockfile changes after `uv sync`** — if you changed dependencies in
  `pyproject.toml`, regenerate the lock with `uv lock` and commit the
  updated `uv.lock`.

## Running Tests

Run the full test suite:

```bash
uv run pytest tests/ -v
```

Run a specific test file, class, or individual test:

```bash
uv run pytest tests/core/test_auth.py
uv run pytest tests/core/test_auth.py::TestTokenMinting
uv run pytest tests/core/test_auth.py::TestTokenMinting::test_mint_token
```

Check coverage (CI enforces a minimum of **80%**, configured via
`fail_under` in `pyproject.toml`):

```bash
uv run pytest --cov=robotsix_github_auth --cov-report=term-missing
```

> **Note:** An autouse fixture clears cached state between tests so that
> each test runs in isolation. You do not need to clear caches manually;
> rely on the fixture rather than sharing state across tests.

## Code Style & Type Checking

Code style and types are enforced in CI, so run these checks locally
before opening a pull request.

### Linting and formatting (ruff)

```bash
uv run ruff check src/ tests/
```

Ruff is configured in `pyproject.toml` with a line length of 100 and the
rule sets `E`, `F`, `I`, `N`, `W`, `UP`, `B`, `C4`, `SIM`, and `S`
(pycodestyle, pyflakes, isort, pep8-naming, pyupgrade, bugbear,
comprehensions, simplify, and bandit security checks). Many issues can be
fixed automatically:

```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

### Type checking (mypy)

```bash
uv run mypy src/
```

mypy runs in **strict** mode against `src/`. New code must be fully
type-annotated; avoid `Any` and `# type: ignore` unless there is no
reasonable alternative, and prefer narrowing types over suppressing
errors.

### Dependency checks (deptry)

```bash
uv run deptry .
```

## Commit Conventions

This project follows [Conventional Commits](https://www.conventionalcommits.org/).
Commit subjects (and pull-request titles) must start with a type prefix:

- `feat:` — a new feature
- `fix:` — a bug fix
- `docs:` — documentation-only changes
- `test:` — adding or adjusting tests
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `ci:` — changes to CI configuration
- `chore:` — maintenance and tooling changes

A `feat:` commit triggers a minor version bump and a `fix:` commit a
patch bump. Breaking changes are marked with `!` after the type
(e.g. `feat!:`) or a `BREAKING CHANGE:` footer.

Releases and the changelog are automated with
[release-please](https://github.com/googleapis/release-please)
(see `release-please-config.json`). **Do not edit `CHANGELOG.md`
manually** — it is generated from commit history.

## Pull Request Guidelines

- Keep pull requests focused on a single logical change.
- Ensure tests, ruff, mypy, and deptry all pass locally before opening
  the PR.
- Add or update tests for any behaviour you change; coverage must stay
  at or above the 80% minimum enforced by CI.
- Give the PR a Conventional Commits-style title (see above).
- Reference this `CONTRIBUTING.md` and describe what changed and why in
  the PR description.
- For anything with security implications, review
  [SECURITY.md](SECURITY.md) and report vulnerabilities privately rather
  than in a public PR or issue.

## Where to Get Help

- **Questions and bug reports** — open an issue on the project's GitHub
  repository.
- **Security vulnerabilities** — follow the process in
  [SECURITY.md](SECURITY.md) (report privately via GitHub Security
  Advisories, not public issues).
- **CI/CD conventions** — see
  [docs/ci/ci-conventions.md](docs/ci/ci-conventions.md) for the
  workflow rules enforced by the `ci-conventions` CI job.
