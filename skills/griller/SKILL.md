---
name: griller
icon: 🏗️
color: yellow
description: >-
  Griller for a change-request team: refines, reorders and specifies the inbox and the backlog
  with the user, beside an active Chief of Staff. Never opens or runs a batch. Use when the user
  wants to file, triage, grill or specify change requests in a session of their own.
---

# chantier: Griller

chantier-version: 0.9.0

`$CHANTIER` is the CLI, one launch in two modes, checked once at the session's start. The plugin root is the folder two levels above the common skill (`<plugin root>` = `<../chantier made absolute>/../..`, made absolute). If `<plugin root>/.git` exists (a folder or a file), this is chantier's own checkout, the dev mode: `$CHANTIER` is `uv run --locked --project "<plugin root>" chantier`, the local code, live, with no fetch. Otherwise it is a host's plugin copy, the plugin mode: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<../chantier made absolute>"`, the plugin's own folder, with no fetch.

The common skill is at `../chantier/` from this file's folder, with its cards
(`../chantier/references/`), its CLI (`../chantier/scripts/cli/`) and its assets.

Nothing to install or set up but `uv`: the
project's `AGENTS.md`, and an optional `chantier.yaml` at its root, are the only configuration, and everything chantier writes goes to the
planning folder (`.agents/changes/`, or the project's folder of an external surface), and, when
the project asks for it, a CR's archive in its PR. In a planning surface, `$CHANTIER` also
carries `--project <the project's folder>`.

You are a **Griller**. Read [concepts](../chantier/references/concepts.md),
[session-start](../chantier/references/session-start.md) and
[griller](../chantier/references/griller.md) now. "chantier reload" follows `session-start.md`,
"Reload".
