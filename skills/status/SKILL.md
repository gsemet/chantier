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

chantier-version: 0.8.0

`$CHANTIER` means `uv run --script "<../chantier made absolute>/scripts/cli/chantier.py"`: the
common skill at `../chantier/` from this file's folder, with its cards (`../chantier/references/`),
its CLI (`../chantier/scripts/cli/`) and its assets. Nothing to install or set up: the
project's `AGENTS.md` is the only configuration.

Read [report](../chantier/references/report.md) now, and nothing else of chantier: not the main
skill, not the Chief of Staff's card, not the introduction. Then, for the active batch, or for
each active batch when there are several (`--batch <batch>`):

1. `$CHANTIER status --refresh` with no epoch;
2. `$CHANTIER status`;
3. `$CHANTIER cost`.

Write the Progress report from their output, in the user's language, in the shape `report.md`
gives.

With no active batch, say so in one line and give the backlog count from
`.agents/changes/STATUS.md`.

You change nothing: no order, no heartbeat, no epoch, no file.
