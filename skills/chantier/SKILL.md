---
name: chantier
icon: 🏗️
color: yellow
description: >-
  The entry that asks which role you want in this session: the Chief of Staff or a Griller,
  then loads that skill. Use when the user addresses chantier
  without a role, and when the user says "chantier reload" (the session reads chantier's rules
  again, typically after a compaction). `/chantier:chief-of-staff` and `/chantier:griller` start a role directly; `/chantier:status` gives the progress report.
---

# chantier: the router

chantier-version: 0.9.0

`$CHANTIER` is the CLI, one launch in two modes, checked once at the session's start. The plugin root is the folder two levels above the common skill (`<plugin root>` = `<this skill's folder>/../..`, made absolute). If `<plugin root>/.git` exists (a folder or a file), this is chantier's own checkout, the dev mode: `$CHANTIER` is `uv run --locked --project "<plugin root>" chantier`, the local code, live, with no fetch. Otherwise it is a host's plugin copy, the plugin mode: `$CHANTIER` is `uvx --from "<plugin root>" chantier --skill "<this skill's folder>"`, the plugin's own folder, with no fetch.

Nothing to install or set up but `uv`: the plugin ships the
agents, the project's `AGENTS.md`, and an optional `chantier.yaml` at its root, are the only configuration, and everything chantier writes goes
to the planning folder (`.agents/changes/`, or the project's folder of an external surface), as
plain JSON and Markdown, and, when the project asks for it, a CR's archive in its PR. In a
planning surface, `$CHANTIER` also carries `--project <the project's folder>`.

Read [concepts](references/concepts.md) and [session-start](references/session-start.md) now,
then follow `session-start.md`'s start checks and seat reading.

With the argument `reload`, or on the words "chantier reload", follow `session-start.md`, section
"5. Reload", and do nothing else of this file: ask no role.

- With **no live Chief of Staff in the seat** (none, or a session that looks stopped): ask the
  user, in one question, which role they want in this session: the Chief of Staff or a Griller.
  Then load that skill by the host's means and follow it: `chief-of-staff` with no argument (its
  mode follows the surface) or `griller`.
- With a **live Chief of Staff in the seat**: ask nothing; behave as `/chantier:chief-of-staff`
  does (its table in `session-start.md`).
