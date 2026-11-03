# AGENTS.md

- Run `just check` before you hand back; it must pass on Linux, macOS and Windows.
- `main` is protected: work on a branch, open a PR, merge by rebase when CI is green.
- The plugin must work with no setup: the user's `AGENTS.md` is the only configuration, and
  chantier writes only in `.agents/changes/`, as plain JSON and Markdown.
- `agents/` (Claude Code) and `com.github.copilot/agents/` (Copilot) are hand-written, one file
  per role and host: change a role on both hosts together; their bodies must stay identical.
- A role's contract lives in `skills/chantier/references/` and travels in the prompt
  `chantier spawn` prints, never in an agent file.
- Never edit a version by hand: `just version X.Y.Z` or `just bump-version [minor|major]`.
- The CLI has no dependencies and must stay portable (POSIX and Windows, UTF-8 everywhere).
- Tests check the structure only (`tests/test_structure.py`): keep them few and fast; the batch
  workflow belongs to `just scenario`.
- Fail, never improvise: no fallback model, tool, agent or workaround in the skill or the CLI.
- Repository text in English. See [CONTRIBUTING.md](CONTRIBUTING.md).
