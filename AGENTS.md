# AGENTS.md

- Run `just check` before you hand back; it must pass on Linux, macOS and Windows.
- `agents/` (Claude Code) and `com.github.copilot/agents/` (Copilot) are generated: edit
  `skills/chantier/assets/agents/` or `skills/chantier/references/models/`, then `just agents`.
- The plugin must work with no setup and write nothing in a user's repository by default.
- Never edit a version by hand: `just version X.Y.Z` or `just bump-version [minor|major]`.
- The CLI has no dependencies and must stay portable (POSIX and Windows, UTF-8 everywhere).
- Tests check the structure only (`tests/test_structure.py`): keep them few and fast; do not test
  the batch workflow there (`just scenario` is the optional end-to-end run).
- Fail, never improvise: no fallback model, tool or workaround in the skill or the CLI.
- Repository text in English. See [CONTRIBUTING.md](CONTRIBUTING.md).
