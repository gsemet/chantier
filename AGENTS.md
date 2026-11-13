# AGENTS.md

- Run `just check` before you hand back; it must pass on Linux, macOS and Windows.
- The long gate is `just scenario`: a change to the CLI, the cards or the scenario passes it
  before its PR; a change to the docs or the eval kit alone needs none.
- A change to `hooks/` or `types/` passes `just mod` before its PR; the agent runs it itself, and
  one that cannot stops and says so, with no workaround.
- `main` is protected: work on a branch, open a PR, merge by rebase when CI is green.
- The plugin must work with no setup: the user's `AGENTS.md`, and an optional `chantier.yaml` at
  the project's root, are the only configuration (with no `chantier.yaml` chantier runs as if it
  were empty), and chantier writes only in the planning folder (`.agents/changes/`, or the project's folder of an
  external planning surface), as plain JSON and Markdown, and a CR's cleaned archive in its PR
  when the project asks for it, and fast-forwards a clean main checkout after a merge it records.
- `agents/` (Claude Code) and `com.github.copilot/agents/` (Copilot) are hand-written, one file
  per role and host: change a role on both hosts together; their bodies must stay identical.
- A role's contract lives in `skills/chantier/references/` (the cards), never in an agent file
  or in the CLI: the parent that starts an agent names the card in its prompt. A card says what
  the role judges; the CLI (`rails.py`) says what it refuses; a user's project rules rank above
  both. The CLI knows no role.
- The CLI's scope: the CR lifecycle, the batch's frame (limits, record, STATUS files), the means
  to synchronise, and a few tools. The agents do the work, git and the forge included; a new
  CLI tool comes from measured token-costly behaviour, never from speculation. One named
  exception: `chantier board`, a read-only web view of the record the CLI already keeps, for the
  user in remote: it writes no file, takes its dependencies through the CLI's PEP 723 inline metadata like the
  rest of the CLI, and knows no role; anything
  more (answering an ask, filing an item) is another CR.
- Never edit a version by hand: `just version X.Y.Z` or `just bump-version [minor|major]`.
- The CLI's dependencies are Python packages declared in its scripts' PEP 723 inline metadata and
  locked beside them; uv installs them at the first run, with no install by the user. A dependency
  ships wheels for Linux, macOS and Windows and replaces hand-written code. The CLI stays portable
  (POSIX and Windows, UTF-8 everywhere).
- Tests check the structure only (`tests/`): keep them few and fast; the batch
  workflow belongs to `just scenario`.
- A session here runs chantier itself, read live from the main checkout: use it to debug it. An
  edit loads at the next session or with `/reload-plugins`, with no reinstall; a worktree's edit
  loads once merged into the main checkout.
- During an eval the main checkout does not change, neither its files nor its branch: any other
  work goes in a worktree. An eval's workspace is outside this repository: it does not read
  `.claude/settings.json` and gets the plugin from the user's own install.
- A change to what the CR board pane draws (`hooks/register.tsx`'s pane, or the `STATUS.json`
  fields of `status.py` that the pane shows) carries, in its PR's Deliverables, one screenshot of
  the pane from a real Claude Code session running the PR's head, captioned with the head's SHA
  (seven characters). Until it is there, the PR's Known gaps names it ("no screenshot of the pane
  from a real session"), so the ready line quotes it; the Chief of Staff then asks the user for
  one. See [CONTRIBUTING.md](CONTRIBUTING.md).
- No fallback: no look-alike model, tool or agent and no workaround in the skill or the CLI; an
  agent judges freely within what it has.
- Repository text in English. See [CONTRIBUTING.md](CONTRIBUTING.md).
