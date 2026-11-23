---
name: chantier
icon: 🏗️
color: yellow
description: >-
  The entry that asks which role you want in this session: the Chief of Staff or a Griller,
  then loads that skill. Use when the user addresses chantier
  without a role, and when the user says "chantier reload". `/chantier:chief-of-staff`, `/chantier:griller` start a role; `/chantier:status` gives the progress report.
---

# chantier: the router

chantier-version: 0.15.1

`$CHANTIER` is the CLI, one launch in two modes, its mode checked once at the session's start. The chantier skill's folder (`<skill folder>` = this file's folder in the `chantier` skill, `../chantier` from it in the other skills, made absolute) and the plugin root (`<plugin root>` = `<skill folder>/../..`, made absolute). If `<plugin root>/.git` exists (a folder or a file), this is chantier's own checkout; when the session's project is chantier (from the session's context, the project it works on: in a planning surface the project folder `projects/chantier`, by its name alone; in-project chantier's own repository, which the plugin manifest at its root confirms, `.claude-plugin/plugin.json` or `.github/plugin/plugin.json` whose `name` is `chantier`; the question is "is the project chantier", never "does it use chantier"), it is the dev mode: sync first, before the first `$CHANTIER` command and at each place the cards name a sync (a batch's start, after a merge that changes `uv.lock`), by `session-start.md`, "6. Sync the checkout" (read it before the first sync). Check first, writing nothing, with `uv sync --locked --check --project "<plugin root>"` (the command inside the rule P10 prints for it): exit 0 is in sync, nothing to sync; exit 1 with uv's text "The environment is outdated" is a sync to run, after the holders of `<plugin root>/.venv` are named; any other exit is an ordinary sync failure, never `sync pending`. Never stop or kill a process for a sync, nor ask anyone to: with a holder, go on unsynced saying `sync pending: held by <holders>`, try again at each next turn but a reload, and tell the user once after 3 minutes. Then `$CHANTIER` is `uv run --no-sync --project "<plugin root>" chantier`, the local code, live, with no fetch; only the steering session syncs, never a Foreman, a Driver or a worker. Otherwise it is the plugin mode, a host's plugin copy or another project, even with the plugin loaded from chantier's checkout: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<skill folder>"`, with no fetch, and the session never runs `uv sync`. Any failure of the sync or of `$CHANTIER`, in either mode, at any call, follows `startup-core.md`, except a sync held as above (`sync pending`). In a planning surface, `$CHANTIER` also carries `--project <the project's folder>`. `<plugin root>` is written absolute, with forward slashes, quoted, the same path as P10's rule holds (the same slashes, drive letter's case and trailing slash; the rule's quoting may differ, per the trial); `$CHANTIER` is carried verbatim into every brief and command, since another form of the path does not match the rule and meets the host's prompt.


## Startup core

- With **no live Chief of Staff in the seat** (none, or a session that looks stopped): ask the
  user which role they want in this session: the Chief of Staff or a Griller.
  Then load that skill and follow it: `chief-of-staff` with no argument (its
  mode follows the surface) or `griller`.
- With a **live Chief of Staff in the seat**: ask nothing; behave as `/chantier:chief-of-staff`
  does (its table in `session-start.md`).

With the argument `reload`, or on "chantier reload", follow `session-start.md`, "5. Reload", nothing else of this file; in a session that holds a role (the message names it, or the seat names this session), that role's skill loads with `reload` instead; with no role, ask none.

The startup reading is named by [startup-manifest.json](references/startup-manifest.json).
