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

`$CHANTIER` is the CLI, one launch in two modes, its mode checked once at the session's start. The chantier skill's folder (`<skill folder>` = this file's folder in the `chantier` skill, `../chantier` from it in the other skills, made absolute) and the plugin root (`<plugin root>` = `<skill folder>/../..`, made absolute). If `<plugin root>/.git` exists (a folder or a file), this is chantier's own checkout; when the session's project is chantier (from the session's context, the project it works on: in a planning surface the project folder `projects/chantier`, by its name alone; in-project chantier's own repository, which the plugin manifest at its root confirms, `.claude-plugin/plugin.json` or `.github/plugin/plugin.json` whose `name` is `chantier`; the question is "is the project chantier", never "does it use chantier"), it is the dev mode: sync first, before the first `$CHANTIER` command and at each place the cards name a sync (a batch's start, after a merge that changes `uv.lock`), by `session-start.md`, "6. Sync the checkout" (read it before the first sync). Check first, writing nothing, with `uv sync --locked --check --project "<plugin root>"` (the command inside the rule P10 prints for it): exit 0 is in sync, nothing to sync; exit 1 with uv's text "The environment is outdated" is a sync to run, after the holders of `<plugin root>/.venv` are named; any other exit is an ordinary sync failure, never `sync pending`. Never stop or kill a process for a sync, nor ask anyone to: with a holder, go on unsynced saying `sync pending: held by <holders>`, try again at each next turn but a reload, and tell the user once after 3 minutes. Then `$CHANTIER` is `uv run --no-sync --project "<plugin root>" chantier`, the local code, live, with no fetch; only the steering session syncs, never a Foreman, a Driver or a worker. Otherwise it is the plugin mode, a host's plugin copy or another project, even with the plugin loaded from chantier's checkout: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<skill folder>"`, with no fetch, and the session never runs `uv sync`. Any failure of the sync or of `$CHANTIER`, in either mode, at any call, follows `startup-core.md`, except a sync held as above (`sync pending`). In a planning surface, `$CHANTIER` also carries `--project <the project's folder>`. `<plugin root>` is written absolute, with forward slashes, quoted, the same path as P10's rule holds (the same slashes, drive letter's case and trailing slash; the rule's quoting may differ, per the trial); `$CHANTIER` is carried verbatim into every brief and command, since another form of the path does not match the rule and meets the host's prompt.

The common skill is at `../chantier/` from this file's folder, with its cards
(`../chantier/references/`), its CLI (`../chantier/scripts/cli/`) and its assets.

## Startup core

You change nothing: no order, no heartbeat, no epoch, no file.

Your startup reading is named by
[startup-manifest.json](../chantier/references/startup-manifest.json). Read
[status-layout](../chantier/references/status-layout.md) only for the status action, and nothing
else of chantier: not the main skill, not the Chief of Staff's card, not the introduction. Then, for
the active batch, or for
each active batch when there are several (`--batch <batch>`):

1. `$CHANTIER status --refresh` with no epoch;
2. `$CHANTIER status`;
3. `$CHANTIER cost`.

Read each CR's icon and label from the batch's `STATUS.md` (the Status column; or `label` in its
`STATUS.json`), just refreshed by step 1: the text output of `status` draws no icon.
Write the Progress report from their output, in the user's language, by the Progress skeleton of `status-layout.md`, with the cost as its tables.

With no active batch, say so in one line and give the backlog count from
`.agents/changes/STATUS.md`.
