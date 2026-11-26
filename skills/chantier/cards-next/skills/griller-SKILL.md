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

`$CHANTIER` is the CLI, one launcher line:

```
uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" [--project <folder>] <command>
```

`<plugin root>` is this skill's folder `../..` made absolute, with forward slashes, quoted. `--project <folder>`, the project's folder in the planning surface, only when the planning lives on an external surface. Carry `$CHANTIER` verbatim into every brief and command, in full, never in a shell variable: another path form misses the allow rule and meets the host's prompt. The launcher picks the mode itself (chantier's own checkout in a chantier session: the local code, live; else the plugin's build).

At a session's start, at a batch's start and after a merge that changes `uv.lock`, the steering session, and no other, syncs, with `--sync` first: `uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" --sync [--project <folder>]`. It prints `in sync`, `synced`, `plugin mode: no sync (only chantier's own checkout syncs)` or `sync pending: held by <holders>` (stop or kill no holder, nor ask anyone to; go on unsynced: [sync-checkout](../chantier/references/sync-checkout.md)).

Exit 127 (`chantier launcher: uv is not on PATH (uv is the one tool chantier needs)`) or any other failure of the launcher is a stop: report its text, never another command. One exception: a `--sync` that fails at a batch's start or after a merge is one line with uv's text, and you go on ([sync-checkout](../chantier/references/sync-checkout.md)).

Cards: `../chantier/references/`; CLI: `../chantier/scripts/cli/`.

You are a **Griller**. Run `$CHANTIER brief griller` and read the file its last line names, whole, first; run it again when your role changes.

With the argument `reload`, or on "chantier reload": run `$CHANTIER help reload`, follow it and run the brief again, with no `--sync`; nothing else of this file but the launcher.
