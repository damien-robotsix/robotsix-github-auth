#!/usr/bin/env python3
"""Validate that all jobs in .github/workflows/ci.yml follow shared conventions.

Scans the CI workflow file and checks that every job includes the step patterns
and parameters that are present in ≥2 existing jobs — preventing agent-generated
PRs from omitting conventions like ``persist-credentials: false`` or
``astral-sh/setup-uv``.

Usage:
    python scripts/check_ci_conventions.py [workflow-file]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped] # deptry: ignore[DEP004]


def _load_composite_action(uses: str, workflow_dir: Path) -> dict[str, Any] | None:
    """If *uses* points to a local composite action, load its action.yml.

    Returns the parsed action definition, or ``None`` if it is not a local
    action or cannot be loaded.
    """
    if not uses.startswith("./"):
        return None
    action_dir = workflow_dir / uses
    action_yml = action_dir / "action.yml"
    if not action_yml.is_file():
        # also try action.yaml
        action_yml = action_dir / "action.yaml"
    if not action_yml.is_file():
        return None
    with open(action_yml) as fh:
        doc: Any = yaml.safe_load(fh)
    if isinstance(doc, dict) and doc.get("runs", {}).get("using") == "composite":
        return doc
    return None


def _expand_steps(steps: list[dict[str, Any]], workflow_dir: Path) -> list[dict[str, Any]]:
    """Recursively expand composite action steps, returning a flat step list."""
    expanded: list[dict[str, Any]] = []
    for step in steps:
        uses = step.get("uses", "")
        action_doc = _load_composite_action(uses, workflow_dir)
        if action_doc is not None:
            inner = action_doc["runs"].get("steps", [])
            expanded.extend(_expand_steps(inner, workflow_dir))
        else:
            expanded.append(step)
    return expanded


def _first_step_uses(step: dict[str, Any], action: str) -> bool:
    uses: str = step.get("uses", "")
    return uses.startswith(action)


def _has_step_using(steps: list[dict[str, Any]], action: str) -> bool:
    return any(s.get("uses", "").startswith(action) for s in steps)


def _runs_uv_command(steps: list[dict[str, Any]]) -> bool:
    """Return True if any step runs a ``uv`` or ``uvx`` command."""
    for step in steps:
        run = step.get("run", "")
        if isinstance(run, str) and ("uv " in run or "uvx " in run or run.startswith("uv ")):
            return True
    return False


def _checkout_steps_missing_persist_credentials(
    steps: list[dict[str, Any]],
) -> list[str]:
    """Return descriptions of checkout steps that lack persist-credentials: false."""
    issues: list[str] = []
    for i, step in enumerate(steps):
        if step.get("uses", "").startswith("actions/checkout"):
            with_block: dict[str, Any] = step.get("with", {})
            if with_block.get("persist-credentials") is not False:
                label: str = step.get("name", f"step {i + 1}")
                issues.append(
                    f"  - {label}: actions/checkout missing ``persist-credentials: false``"
                )
    return issues


def _find_repo_root(path: str) -> Path:
    """Find the repository root by walking up from *path* until .git/ is found."""
    p = Path(path).resolve().parent
    while p != p.parent:
        if (p / ".git").is_dir():
            return p
        p = p.parent
    # Fallback: assume 2 levels up from .github/workflows/
    return Path(path).resolve().parent.parent.parent


def check_workflow(path: str, *, workflow_dir: Path | None = None) -> list[str]:
    """Validate *path* (a GitHub Actions workflow YAML) and return a list of issues."""
    errors: list[str] = []
    if workflow_dir is None:
        # Local composite actions (uses: ./...) are resolved relative to
        # the repository root, not the workflow file's directory.
        workflow_dir = _find_repo_root(path)

    with open(path) as fh:
        doc: Any = yaml.safe_load(fh)

    if not isinstance(doc, dict):
        errors.append("Workflow root is not a mapping.")
        return errors

    jobs = doc.get("jobs", {})
    if not jobs:
        errors.append("No jobs found in workflow.")
        return errors

    for job_name, job_def in jobs.items():
        steps = job_def.get("steps", [])
        if not steps:
            errors.append(f"[{job_name}] No steps defined.")
            continue

        # Expand composite actions so their internal steps are visible
        # to all convention checks.
        expanded_steps = _expand_steps(steps, workflow_dir)

        # 1. Every job MUST have step-security/harden-runner as first step.
        if not expanded_steps or not _first_step_uses(
            expanded_steps[0], "step-security/harden-runner"
        ):
            first_uses = expanded_steps[0].get("uses", "<none>") if expanded_steps else "<none>"
            errors.append(
                f"[{job_name}] First step is not step-security/harden-runner "
                f"(found: {first_uses})."
            )

        # 2. Every actions/checkout step MUST have persist-credentials: false.
        errors.extend(
            f"[{job_name}] {issue}"
            for issue in _checkout_steps_missing_persist_credentials(expanded_steps)
        )

        # 3. Every job that runs ``uv`` MUST have astral-sh/setup-uv.
        if _runs_uv_command(expanded_steps) and not _has_step_using(
            expanded_steps, "astral-sh/setup-uv"
        ):
            errors.append(f"[{job_name}] Runs uv/uvx but has no astral-sh/setup-uv step.")

        # 4. Every job using ``uv sync`` MUST pass ``--frozen``.
        for step in expanded_steps:
            run = step.get("run", "")
            if isinstance(run, str) and "uv sync" in run and "--frozen" not in run:
                errors.append(f"[{job_name}] ``uv sync`` without ``--frozen`` flag.")

    return errors


def main() -> None:
    workflow_path = sys.argv[1] if len(sys.argv) > 1 else ".github/workflows/ci.yml"
    errors = check_workflow(workflow_path)

    if errors:
        print(f"CI workflow convention violations in {workflow_path}:")
        for err in errors:
            print(err)
        print(f"\n{len(errors)} violation(s) found.")
        sys.exit(1)

    print(f"✓ {workflow_path} follows all CI conventions.")
    sys.exit(0)


if __name__ == "__main__":
    main()
