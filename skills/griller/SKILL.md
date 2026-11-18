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

chantier-version: 0.13.0

`$CHANTIER` is the CLI, one launch in two modes, checked once at the session's start. The plugin root (`<plugin root>` = `<../chantier made absolute>/../..`, made absolute). If `<plugin root>/.git` exists (a folder or a file), this is chantier's own checkout, the dev mode: run `uv sync --locked --project "<plugin root>"` once, before the first `$CHANTIER` command, then `$CHANTIER` is `uv run --no-sync --project "<plugin root>" chantier`, the local code, live, with no fetch; only the steering session syncs, never a Foreman, a Driver or a worker. Otherwise it is a host's plugin copy, the plugin mode: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<../chantier made absolute>"`, with no fetch. Any failure of the sync or of `$CHANTIER`, in either mode, at any call, follows `startup-core.md`.

The common skill is at `../chantier/` from this file's folder, with its cards
(`../chantier/references/`), its CLI (`../chantier/scripts/cli/`) and its assets.

Everything chantier writes goes to the
planning folder (`.agents/changes/`, or the project's folder of an external surface), and, when
the project asks for it, a CR's archive in its PR. In a planning surface, `$CHANTIER` also
carries `--project <the project's folder>`.

## Startup core

You are a **Griller**; your startup reading is named by
[startup-manifest.json](../chantier/references/startup-manifest.json). At the session's start,
read `session-start.md` (the manifest's `session-start` action).
With the argument `reload`, or on the words "chantier reload", follow `session-start.md`, "5. Reload", with $CHANTIER as this file defines it but no uv sync; nothing else of this file.
