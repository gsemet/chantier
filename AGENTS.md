# AGENTS.md

- Run `just check` before you hand back; it must pass on Linux, macOS and Windows.
- `agents/` is generated: edit `skills/chantier/assets/agents/` or
  `skills/chantier/references/models/`, then run `just agents`.
- Never edit a version by hand: `just version X.Y.Z` or `just bump-version [minor|major]`.
- The CLI has no dependencies and must stay portable (POSIX and Windows); every CLI change gets
  a unit test in `skills/chantier/scripts/cli/tests/`.
- Fail, never improvise: no fallback model, tool or workaround in the skill or the CLI.
- Repository text in English. See [CONTRIBUTING.md](CONTRIBUTING.md).
