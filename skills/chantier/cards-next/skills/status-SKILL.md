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

chantier-version: 0.15.1

`$CHANTIER` is the CLI, one launcher line:

```
uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" [--project <folder>] <command>
```

`<plugin root>` is this skill's folder `../..` made absolute, with forward slashes, quoted. `--project <folder>`, the project's folder in the planning surface, only when the planning lives on an external surface. Carry `$CHANTIER` verbatim into every brief and command, in full, never in a shell variable: another path form misses the allow rule and meets the host's prompt. The launcher picks the mode itself (chantier's own checkout in a chantier session: the local code, live; else the plugin's build).

At a session's start, at a batch's start and after a merge that changes `uv.lock`, the steering session, and no other, syncs, with `--sync` first: `uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" --sync [--project <folder>]`. It prints `in sync`, `synced`, `plugin mode: no sync (only chantier's own checkout syncs)` or `sync pending: held by <holders>` (stop or kill no holder, nor ask anyone to; go on unsynced: [sync-checkout](../chantier/references/sync-checkout.md)).

Exit 127 (`chantier launcher: uv is not on PATH (uv is the one tool chantier needs)`) or any other failure of the launcher is a stop: report its text, never another command. One exception: a `--sync` that fails at a batch's start or after a merge is one line with uv's text, and you go on ([sync-checkout](../chantier/references/sync-checkout.md)).

Cards: `../chantier/references/`; CLI: `../chantier/scripts/cli/`.

You change nothing: no order, no heartbeat, no epoch, no file.

Read [status-layout](../chantier/references/status-layout.md), only for this action, and nothing else of chantier: not the main skill, not the Chief of Staff's card, not the introduction. Then, for the active batch, or each active batch when there are several (`--batch <batch>`):

1. `$CHANTIER status --refresh` with no epoch;
2. `$CHANTIER status`;
3. `$CHANTIER cost`.

Read each CR's icon and label from the batch's `STATUS.md` (the Status column; or `label` in its `STATUS.json`), just refreshed by step 1: the text output of `status` draws no icon. Write the Progress report from their output, in the user's language, by the Progress skeleton of status-layout, with the cost as its tables.

With no active batch, say so in one line and give the backlog count from `.agents/changes/STATUS.md`.
