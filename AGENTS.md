# AGENTS.md

- Run `just check` before you hand back; it must pass on Linux, macOS and Windows.
- The long gate is `just scenario`: a change to the CLI, the cards or the scenario passes it
  before its PR; a change to the docs or the eval kit alone needs none.
- `main` is protected: work on a branch, open a PR, merge by rebase when CI is green.
- The plugin must work with no setup: the user's `AGENTS.md` is the only configuration, and
  chantier writes only in `.agents/changes/`, as plain JSON and Markdown.
- `agents/` (Claude Code) and `com.github.copilot/agents/` (Copilot) are hand-written, one file
  per role and host: change a role on both hosts together; their bodies must stay identical.
- A role's contract lives in `skills/chantier/references/` (the cards), never in an agent file
  or in the CLI: the parent that starts an agent names the card in its prompt. A card says what
  the role judges; the CLI (`rails.py`) says what it refuses; a user's project rules rank above
  both. The CLI knows no role.
- The CLI's scope: the CR lifecycle, the batch's frame (limits, record, STATUS files), the means
  to synchronise, and a few tools. The agents do the work, git and the forge included; a new
  CLI tool comes from measured token-costly behaviour, never from speculation.
- Never edit a version by hand: `just version X.Y.Z` or `just bump-version [minor|major]`.
- The CLI has no dependencies and must stay portable (POSIX and Windows, UTF-8 everywhere).
- Tests check the structure only (`tests/test_structure.py`): keep them few and fast; the batch
  workflow belongs to `just scenario`.
- A session here runs chantier itself, read live from the main checkout: use it to debug it. An
  edit loads at the next session or with `/reload-plugins`, with no reinstall; a worktree's edit
  loads once merged into the main checkout.
- During an eval the main checkout does not change, neither its files nor its branch: any other
  work goes in a worktree. An eval's workspace is outside this repository: it does not read
  `.claude/settings.json` and gets the plugin from the user's own install.
- No fallback: no look-alike model, tool or agent and no workaround in the skill or the CLI; an
  agent judges freely within what it has.
- Repository text in English. See [CONTRIBUTING.md](CONTRIBUTING.md).
