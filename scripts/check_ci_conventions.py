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
from typing import Any

import yaml  # type: ignore[import-untyped] # deptry: ignore[DEP004]


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


def check_workflow(path: str) -> list[str]:
    """Validate *path* (a GitHub Actions workflow YAML) and return a list of issues."""
    errors: list[str] = []

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

        # 1. Every job MUST have step-security/harden-runner as first step.
        if not _first_step_uses(steps[0], "step-security/harden-runner"):
            errors.append(
                f"[{job_name}] First step is not step-security/harden-runner "
                f"(found: {steps[0].get('uses', '<none>')})."
            )

        # 2. Every actions/checkout step MUST have persist-credentials: false.
        errors.extend(
            f"[{job_name}] {issue}" for issue in _checkout_steps_missing_persist_credentials(steps)
        )

        # 3. Every job that runs ``uv`` MUST have astral-sh/setup-uv.
        if _runs_uv_command(steps) and not _has_step_using(steps, "astral-sh/setup-uv"):
            errors.append(f"[{job_name}] Runs uv/uvx but has no astral-sh/setup-uv step.")

        # 4. Every job using ``uv sync`` MUST pass ``--frozen``.
        for step in steps:
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
