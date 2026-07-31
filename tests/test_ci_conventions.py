"""Tests for scripts/check_ci_conventions.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

# Import the check_workflow function from the scripts module.
_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "check_ci_conventions", _scripts_dir / "check_ci_conventions.py"
)
assert _spec is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["check_ci_conventions"] = _module
assert _spec.loader is not None
_spec.loader.exec_module(_module)
check_workflow = _module.check_workflow


def _write_workflow(tmp_path: Path, doc: dict, *, workflow_filename: str = "ci.yml") -> Path:
    """Write *doc* as a YAML workflow file under *tmp_path* and return its path."""
    wf = tmp_path / workflow_filename
    wf.write_text(yaml.dump(doc))
    return wf


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal repo root (with .git/) at *tmp_path* so _find_repo_root works."""
    (tmp_path / ".git").mkdir()
    return tmp_path


def _write_composite_action(root: Path, rel_dir: str, steps: list[dict]) -> None:
    """Write a composite action.yml at *root*/*rel_dir*/action.yml."""
    action_dir = root / rel_dir
    action_dir.mkdir(parents=True, exist_ok=True)
    action_yml = action_dir / "action.yml"
    action_yml.write_text(yaml.dump({"runs": {"using": "composite", "steps": steps}}))


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

VALID_WORKFLOW: dict = {
    "on": "push",
    "jobs": {
        "lint": {
            "runs-on": "ubuntu-latest",
            "steps": [
                {"uses": "step-security/harden-runner@v2"},
                {
                    "uses": "actions/checkout@v4",
                    "with": {"persist-credentials": False},
                },
                {"uses": "astral-sh/setup-uv@v5"},
                {"run": "uv sync --frozen"},
                {"run": "uv run ruff check ."},
            ],
        },
    },
}


def test_happy_path_valid_workflow(tmp_path: Path) -> None:
    """A valid workflow with all conventions satisfied yields zero errors."""
    root = _make_repo(tmp_path)
    wf = _write_workflow(root, VALID_WORKFLOW)
    errors = check_workflow(str(wf))
    assert errors == []


# ---------------------------------------------------------------------------
# Missing harden-runner
# ---------------------------------------------------------------------------


def test_missing_harden_runner_first_step_not_harden(tmp_path: Path) -> None:
    """First step is checkout instead of harden-runner → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "harden-runner" in errors[0]


# ---------------------------------------------------------------------------
# Missing persist-credentials: false
# ---------------------------------------------------------------------------


def test_missing_persist_credentials(tmp_path: Path) -> None:
    """Checkout without persist-credentials: false → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {"uses": "actions/checkout@v4"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "persist-credentials" in errors[0]


def test_persist_credentials_true_is_also_an_error(tmp_path: Path) -> None:
    """persist-credentials: true is not the same as false → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": True},
                    },
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "persist-credentials" in errors[0]


# ---------------------------------------------------------------------------
# Missing astral-sh/setup-uv
# ---------------------------------------------------------------------------


def test_missing_setup_uv(tmp_path: Path) -> None:
    """Job runs uv without astral-sh/setup-uv → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"run": "uv run pytest"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "astral-sh/setup-uv" in errors[0]


def test_uvx_without_setup_uv(tmp_path: Path) -> None:
    """Job runs uvx without astral-sh/setup-uv → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"run": "uvx deptry ."},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "astral-sh/setup-uv" in errors[0]


# ---------------------------------------------------------------------------
# Missing --frozen on uv sync
# ---------------------------------------------------------------------------


def test_missing_frozen_on_uv_sync(tmp_path: Path) -> None:
    """uv sync without --frozen → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"uses": "astral-sh/setup-uv@v5"},
                    {"run": "uv sync"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "--frozen" in errors[0]


def test_frozen_flag_is_checked_per_step(tmp_path: Path) -> None:
    """One step has frozen, another doesn't — only the unfrozen one errors."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"uses": "astral-sh/setup-uv@v5"},
                    {"run": "uv sync --frozen"},
                    {"run": "uv sync"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "--frozen" in errors[0]


# ---------------------------------------------------------------------------
# Composite action expansion
# ---------------------------------------------------------------------------


def test_composite_action_satisfies_setup_uv(tmp_path: Path) -> None:
    """A job using a local composite action that contains setup-uv passes check."""
    root = _make_repo(tmp_path)
    # Write a composite action that internally uses astral-sh/setup-uv.
    _write_composite_action(
        root,
        ".github/actions/setup",
        [{"uses": "astral-sh/setup-uv@v5"}],
    )
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"uses": "./.github/actions/setup"},
                    {"run": "uv sync --frozen"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert errors == []


def test_composite_action_expands_inner_steps_for_harden_runner(
    tmp_path: Path,
) -> None:
    """Hardening check sees through composite actions."""
    root = _make_repo(tmp_path)
    _write_composite_action(
        root,
        ".github/actions/setup",
        [
            {"uses": "step-security/harden-runner@v2"},
            {"uses": "astral-sh/setup-uv@v5"},
        ],
    )
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "./.github/actions/setup"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"run": "uv sync --frozen"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert errors == []


def test_composite_action_expands_inner_steps_for_persist_credentials(
    tmp_path: Path,
) -> None:
    """persist-credentials check sees through composite actions that contain checkout."""
    root = _make_repo(tmp_path)
    _write_composite_action(
        root,
        ".github/actions/checkout-wrapper",
        [{"uses": "actions/checkout@v4"}],
    )
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {"uses": "./.github/actions/checkout-wrapper"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "persist-credentials" in errors[0]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_jobs(tmp_path: Path) -> None:
    """Empty jobs dict → error."""
    root = _make_repo(tmp_path)
    doc: dict = {"on": "push", "jobs": {}}
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "No jobs" in errors[0]


def test_malformed_yaml_not_a_dict(tmp_path: Path) -> None:
    """A workflow whose root is a list, not a mapping → error."""
    wf = tmp_path / "ci.yml"
    wf.write_text("- just a list\n")
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "not a mapping" in errors[0]


def test_job_without_steps_key(tmp_path: Path) -> None:
    """A job definition missing 'steps' → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "No steps" in errors[0]


def test_job_with_empty_steps(tmp_path: Path) -> None:
    """A job with an empty steps list → error."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    assert len(errors) == 1
    assert "No steps" in errors[0]


def test_multiple_jobs_all_violations(tmp_path: Path) -> None:
    """Multiple jobs, each with different violations — all caught."""
    root = _make_repo(tmp_path)
    doc: dict = {
        "on": "push",
        "jobs": {
            "job1": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                ],
            },
            "job2": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"run": "uv sync"},
                ],
            },
        },
    }
    wf = _write_workflow(root, doc)
    errors = check_workflow(str(wf))
    # job1: harden-runner missing + persist-credentials missing = 2
    # job2: no astral-sh/setup-uv + --frozen missing = 2
    assert len(errors) == 4


def test_workflow_dir_explicit_override(tmp_path: Path) -> None:
    """Explicit workflow_dir overrides auto-detection from the workflow path."""
    # Create a repo-like structure in a subdirectory.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    _write_composite_action(
        repo_root,
        ".github/actions/setup",
        [{"uses": "astral-sh/setup-uv@v5"}],
    )

    # Write the workflow outside the repo root (e.g. in tmp_path directly).
    doc: dict = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "step-security/harden-runner@v2"},
                    {
                        "uses": "actions/checkout@v4",
                        "with": {"persist-credentials": False},
                    },
                    {"uses": "./.github/actions/setup"},
                    {"run": "uv sync --frozen"},
                ],
            },
        },
    }
    wf = _write_workflow(tmp_path, doc)
    errors = check_workflow(str(wf), workflow_dir=repo_root)
    assert errors == []
