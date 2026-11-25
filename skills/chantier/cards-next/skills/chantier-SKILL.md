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

`$CHANTIER` is the CLI, one launcher line:

```
uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" [--project <folder>] <command>
```

`<plugin root>` is this skill's folder `../..` made absolute, with forward slashes, quoted. `--project <folder>`, the project's folder in the planning surface, only when the planning lives on an external surface. Carry `$CHANTIER` verbatim into every brief and command: another path form misses the allow rule and meets the host's prompt. The launcher picks the mode itself (chantier's own checkout in a chantier session: the local code, live; else the plugin's build).

At a session's start, at a batch's start and after a merge that changes `uv.lock`, the steering session, and no other, syncs, with `--sync` first: `uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" --sync [--project <folder>]`. It prints `in sync`, `synced`, `plugin mode: no sync (only chantier's own checkout syncs)` or `sync pending: held by <holders>` (stop or kill no holder; go on unsynced: [sync-checkout](../chantier/references/sync-checkout.md)).

Exit 127 (`chantier launcher: uv is not on PATH (uv is the one tool chantier needs)`) or any other failure of the launcher is a stop: report its text, never another command. One exception: a `--sync` that fails at a batch's start or after a merge is one line with uv's text, and you go on ([sync-checkout](../chantier/references/sync-checkout.md)).

- With **no live Chief of Staff in the seat** (none, or a session that looks stopped): ask the user which role they want in this session, the Chief of Staff or a Griller, then load that skill and follow it: `chief-of-staff` with no argument (its mode follows the surface) or `griller`.
- With a **live Chief of Staff in the seat**: ask nothing; behave as `/chantier:chief-of-staff` does.

Read the seat with `$CHANTIER seat`; what "live" means: `$CHANTIER help seat`. With the argument `reload`, or on "chantier reload", run `$CHANTIER help reload` and follow it, nothing else of this file but the launcher; a session that holds a role (the message names it, or the seat names this session) loads that role's skill with `reload` instead; with no role, ask none.
