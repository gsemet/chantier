---
name: status
icon: 📋
color: blue
description: >-
  Progress report of the running batch, at once and in the same shape as the Chief of Staff's.
  Changes nothing: no order, no heartbeat, no epoch. Use when the user asks for the status, the
  progress or the cost of a batch, in any session.
---

# chantier: status

chantier-version: 0.9.0

`$CHANTIER` is the CLI, one launch in two modes, checked once at the session's start. The plugin root is the folder two levels above the common skill (`<plugin root>` = `<../chantier made absolute>/../..`, made absolute). If `<plugin root>/.git` exists (a folder or a file), this is chantier's own checkout, the dev mode: `$CHANTIER` is `uv run --locked --project "<plugin root>" chantier`, the local code, live, with no fetch. Otherwise it is a host's plugin copy, the plugin mode: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<../chantier made absolute>"`, the plugin's own folder, with no fetch.

The common skill is at `../chantier/` from this file's folder, with its cards
(`../chantier/references/`), its CLI (`../chantier/scripts/cli/`) and its assets.

Nothing to install or set up but `uv`: the
project's `AGENTS.md`, and an optional `chantier.yaml` at its root, are the only configuration.

Read [status-layout](../chantier/references/status-layout.md) now, and nothing else of chantier: not the main
skill, not the Chief of Staff's card, not the introduction. Then, for the active batch, or for
each active batch when there are several (`--batch <batch>`):

1. `$CHANTIER status --refresh` with no epoch;
2. `$CHANTIER status`;
3. `$CHANTIER cost`.

Read each CR's icon and label from the batch's `STATUS.md` (the Status column; or `label` in its
`STATUS.json`), just refreshed by step 1: the text output of `status` draws no icon.
Write the Progress report from their output, in the user's language, by the Progress skeleton of `status-layout.md`, with the cost as its tables.

With no active batch, say so in one line and give the backlog count from
`.agents/changes/STATUS.md`.

You change nothing: no order, no heartbeat, no epoch, no file.
