# Changelog fragments

Place individual changelog fragment files in this directory.
Each fragment describes a single user-facing change in a future release.

Fragments are managed by [towncrier](https://github.com/twisted/towncrier).
Name your fragment `<issue>.<type>` (e.g. `123.added`, `456.fixed`) —
the file must have **no extension**.  Supported types:

- `added` — a new feature
- `changed` — a change to existing functionality
- `fixed` — a bug fix
- `removed` — a feature removal

Run `towncrier check --compare-with origin/main` to verify your PR has
at least one fragment.  During a release, `towncrier build --version X.Y.Z`
renders all pending fragments into `CHANGELOG.md` and removes them.
