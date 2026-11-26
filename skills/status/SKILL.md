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

`$CHANTIER` is the CLI, one launch in two modes, its mode checked once at the session's start. `<skill folder>` is the `chantier` skill's folder (this file's folder there, `../chantier` from the other skills) and `<plugin root>` is `<skill folder>/../..`, both made absolute. If `<plugin root>/.git` exists (folder or file), this is chantier's own checkout; when the session's project is chantier (in a planning surface the folder `projects/chantier`, by its name alone; in-project the repository whose root `.claude-plugin/plugin.json` or `.github/plugin/plugin.json` has `name` `chantier`; "is the project chantier", never "does it use chantier"), it is the dev mode: sync by `sync-checkout.md` (read it first) before the first `$CHANTIER` command and wherever the cards name one (a batch's start, after a merge that changes `uv.lock`). Check first, writing nothing, with `uv sync --locked --check --project "<plugin root>"` (the command P10's rule holds): exit 0, in sync; exit 1 with uv's "The environment is outdated", a sync to run once the holders of `<plugin root>/.venv` are named; any other exit, an ordinary sync failure, never `sync pending`. Never stop or kill a process for a sync, nor ask anyone to: with a holder, go on unsynced saying `sync pending: held by <holders>`, try again at each next turn but a reload, and tell the user once after 3 minutes. Then `$CHANTIER` is `uv run --no-sync --project "<plugin root>" chantier`, the local code, live, with no fetch; only the steering session syncs. Otherwise it is the plugin mode, a host's plugin copy or another project, even with the plugin loaded from chantier's checkout: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<skill folder>"`, with no fetch, and the session never runs `uv sync`. Any failure of the sync or of `$CHANTIER`, in either mode, at any call, is a stop: report its exact error (floor 4), except a sync held as above (`sync pending`). In a planning surface, `$CHANTIER` also carries `--project <the project's folder>`. `<plugin root>` is written absolute, with forward slashes, quoted, the same path as P10's rule holds (slashes, drive letter's case, trailing slash; the quoting may differ, per the trial); carry `$CHANTIER` verbatim into every brief and command: another path form misses the rule and meets the host's prompt.

Cards: `../chantier/references/`; CLI: `../chantier/scripts/cli/`.

You change nothing: no order, no heartbeat, no epoch, no file.

Read [status-layout](../chantier/references/status-layout.md), only for this action, and nothing else of chantier: not the main skill, not the Chief of Staff's card, not the introduction. Then, for the active batch, or each active batch when there are several (`--batch <batch>`):

1. `$CHANTIER status --refresh` with no epoch;
2. `$CHANTIER status`;
3. `$CHANTIER cost`.

Read each CR's icon and label from the batch's `STATUS.md` (the Status column; or `label` in its `STATUS.json`), just refreshed by step 1: the text output of `status` draws no icon. Write the Progress report from their output, in the user's language, by the Progress skeleton of status-layout, with the cost as its tables.

With no active batch, say so in one line and give the backlog count from `.agents/changes/STATUS.md`.
