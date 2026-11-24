---
name: griller
icon: 🏗️
color: yellow
description: >-
  Griller for a change-request team: refines, reorders and specifies the inbox and the backlog
  with the user, beside an active Chief of Staff. Never opens or runs a batch. Use when the user
  wants to file, triage, grill or specify change requests in a session of their own.
  The argument `reload` reloads its rules after a compaction.
---

# chantier: Griller

chantier-version: 0.15.1

`$CHANTIER` is the CLI, one launch in two modes, its mode checked once at the session's start. `<skill folder>` is the `chantier` skill's folder (this file's folder there, `../chantier` from the other skills) and `<plugin root>` is `<skill folder>/../..`, both made absolute. If `<plugin root>/.git` exists (folder or file), this is chantier's own checkout; when the session's project is chantier (in a planning surface the folder `projects/chantier`, by its name alone; in-project the repository whose root `.claude-plugin/plugin.json` or `.github/plugin/plugin.json` has `name` `chantier`; "is the project chantier", never "does it use chantier"), it is the dev mode: sync by `sync-checkout.md` (read it first) before the first `$CHANTIER` command and wherever the cards name one (a batch's start, after a merge that changes `uv.lock`). Check first, writing nothing, with `uv sync --locked --check --project "<plugin root>"` (the command P10's rule holds): exit 0, in sync; exit 1 with uv's "The environment is outdated", a sync to run once the holders of `<plugin root>/.venv` are named; any other exit, an ordinary sync failure, never `sync pending`. Never stop or kill a process for a sync, nor ask anyone to: with a holder, go on unsynced saying `sync pending: held by <holders>`, try again at each next turn but a reload, and tell the user once after 3 minutes. Then `$CHANTIER` is `uv run --no-sync --project "<plugin root>" chantier`, the local code, live, with no fetch; only the steering session syncs. Otherwise it is the plugin mode, a host's plugin copy or another project, even with the plugin loaded from chantier's checkout: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<skill folder>"`, with no fetch, and the session never runs `uv sync`. Any failure of the sync or of `$CHANTIER`, in either mode, at any call, follows `startup-core.md`, except a sync held as above (`sync pending`). In a planning surface, `$CHANTIER` also carries `--project <the project's folder>`. `<plugin root>` is written absolute, with forward slashes, quoted, the same path as P10's rule holds (slashes, drive letter's case, trailing slash; the quoting may differ, per the trial); carry `$CHANTIER` verbatim into every brief and command: another path form misses the rule and meets the host's prompt.

Cards: `../chantier/references/`; CLI: `../chantier/scripts/cli/`.

## Startup core

You are a **Griller**; your startup reading is named by
`startup-manifest.json`. At the session's start,
read `session-start.md`, then your role's file there, again when the role changes.
With the argument `reload`, or on the words "chantier reload", follow `session-start.md`, "5. Reload", with $CHANTIER as this file defines it but no uv sync; nothing else of this file.
