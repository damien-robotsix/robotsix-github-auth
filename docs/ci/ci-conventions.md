# CI workflow conventions

All jobs in `.github/workflows/ci.yml` MUST follow these shared conventions.
These are verified automatically by the `ci-conventions` CI job; PRs that
introduce violations will be blocked at review time.

## Mandatory conventions (every job)

1. **First step: `step-security/harden-runner`**
   Every job must begin with the hardened runner step configured with
   `egress-policy: audit`:
   ```yaml
   - uses: step-security/harden-runner@0634a2670c59f64b4a01f0f96f84700a4088b9f0  # v2.12.0
     with:
       egress-policy: audit
   ```

2. **Every `actions/checkout` step: `persist-credentials: false`**
   Any checkout step must explicitly disable credential persistence:
   ```yaml
   - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4
     with:
       persist-credentials: false
   ```

3. **Jobs that run `uv`/`uvx` commands: include `astral-sh/setup-uv`**
   Any job that invokes `uv`, `uvx`, `uv sync`, `uv run`, etc. must
   include the `astral-sh/setup-uv` action before the first `uv` invocation:
   ```yaml
   - uses: astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86  # v5
   ```

## Strongly recommended conventions

4. **`uv sync` must use `--frozen`**
   Prevents accidental lockfile mutation in CI:
   ```yaml
   - run: uv sync --frozen --extra dev
   ```

## Rationale

These conventions emerged from repeated CI failures caused by agent-generated
PRs that added new jobs in isolation without scanning the existing workflow
for shared patterns.  Missing `persist-credentials: false` triggered zizmor
`artipacked` findings; missing `astral-sh/setup-uv` caused `uvx: command not
found`.  Enforcing these rules in CI prevents regressions regardless of how
the workflow file is authored.
