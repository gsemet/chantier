---
name: chantier
icon: 🏗️
color: yellow
description: >-
  The entry that asks which role you want in this session: the Chief of Staff (with a Foreman,
  or in direct mode) or a Griller, then loads that skill. Use when the user addresses chantier
  without a role. `/chantier:chief-of-staff` and `/chantier:griller` start a role directly; `/chantier:status` gives the progress report.
---

# chantier: the router

chantier-version: 0.8.0

`$CHANTIER` means `uv run --script "<this skill's folder>/scripts/cli/chantier.py"`, with the
absolute path of the folder this file is in. Nothing to install or set up: the plugin ships the
agents, the project's `AGENTS.md` is the only configuration, and everything chantier writes goes
to the planning folder (`.agents/changes/`, or the project's folder of an external surface), as
plain JSON and Markdown, and, when the project asks for it, a CR's archive in its PR. In a
planning surface, `$CHANTIER` also carries `--project <the project's folder>`.

Read [concepts](references/concepts.md) and [session-start](references/session-start.md) now,
then follow `session-start.md`'s start checks and seat reading.

- With **no live Chief of Staff in the seat** (none, or a session that looks stopped): ask the
  user, in one question, which role they want in this session: the Chief of Staff (Foreman mode),
  the Chief of Staff in direct mode, or a Griller. Then load that skill by the host's means and
  follow it: `chief-of-staff` (with the argument `direct` for the second) or `griller`.
- With a **live Chief of Staff in the seat**: ask nothing; behave as `/chantier:chief-of-staff`
  does (its table in `session-start.md`).
