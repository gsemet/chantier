# Incidents

The stories behind rules that the cards state without their reason: what happened, on which date,
the rule it gave, and where that rule lives now. A story already told in
[the Claude Code trials](proofs/claude-code.md) is linked there, not copied. A rule changes in
its card, topic, floor line or refusal, never here.

## A worktree session could not move to the main checkout (2026-11-10)

- What happened: [Classes of session](proofs/claude-code.md#other-classes-of-session),
  `change_directory`.
- Rule: a session in a worktree cannot move to the main checkout; the user starts a new session
  there.
- Where it lives: [`chantier help host-sessions`](../skills/chantier/references/topics/host-sessions.md).

## A steering session's refused push (2026-11-11)

- What happened: [Auto mode](proofs/claude-code.md#auto-mode), batch-09.
- Rule: a refused force push of a CR's branch goes up from the Driver to its steering session,
  then to the Chief of Staff, then to the user.
- Where it lives: [`chantier help refused-push`](../skills/chantier/references/topics/refused-push.md).

## Auto-fix events on a batch's pull requests (2026-11-12)

- What happened: [Auto-fix events](proofs/claude-code.md#other-auto-fix-events), batch-14 and a
  real-direct eval run.
- Rule: an event is not an order; a CR with a live Driver is left to it.
- Where it lives: [`chantier help host-auto-fix`](../skills/chantier/references/topics/host-auto-fix.md).

## Allow rules counted as strings (before 0.9.0, 2026-11-13)

- What happened: [Who reads it, when](proofs/claude-code.md#who-reads-it-when).
- Rule: preflight's P10 counts commands, not rule strings, so an older count is not comparable.
- Where it lives: [`chantier help host-configuration`](../skills/chantier/references/topics/host-configuration.md).

## The classifier refused loops and stack updates (2026-11-13)

- What happened: [Auto mode](proofs/claude-code.md#auto-mode), batch-15.
- Rule: one command per branch: a loop, a script or a chain matches no prefix rule, so the
  classifier judges it alone.
- Where it lives: the [stack driver's card](../skills/chantier/references/stack-driver.md),
  "Never", and [`chantier help host-auto-mode`](../skills/chantier/references/topics/host-auto-mode.md).

## Long sessions and compaction (2026-11-13 and 2026-11-15)

- What happened: [Compacting](proofs/claude-code.md#compact): how long steering sessions last,
  and where agents and sessions compacted.
- Rule: the recommended `autoCompactWindow` for the steering sessions, unproved; the plugin's
  agents carry their own window.
- Where it lives: [`chantier help host-compact`](../skills/chantier/references/topics/host-compact.md).

## The Foreman's turn-end notices cost steering calls (2026-11-15)

- What happened:
  [The Foreman's turn-end notice](proofs/claude-code.md#other-the-foremans-turn-end-notice),
  real-foreman run 2.
- Rule: on a turn that a notice alone started, the Chief of Staff ends the turn at once, with no
  tool call.
- Where it lives: [`chantier help host-turn-end`](../skills/chantier/references/topics/host-turn-end.md).

## A shell inside a folder blocked its move on Windows (2026-11-18, 2026-11-22)

- What happened: on Windows a process whose current folder is inside a folder keeps that folder
  from being moved or removed (WinError 32), so a CR's move between stages or a worktree's removal
  fails. A background task left running also wakes its owner each time it reports.
- Rule: no shell call changes its folder into a CR folder, and whoever starts a background task
  stops it once it no longer counts. The CLI waits up to 10 s for a held CR folder, then refuses
  with the likely holders.
- Where it lives: `chantier help session-shell`
  ([stopping a task](../skills/chantier/references/topics/session-shell-p1.md),
  [the folder rule](../skills/chantier/references/topics/session-shell-p2.md)),
  [`chantier help worker-shell`](../skills/chantier/references/topics/worker-shell.md), and the
  CLI's refusal of a CR folder move.

## A second stack driver started on silence (2026-11-20)

- What happened: [A Driver's silence](proofs/claude-code.md#other-a-drivers-silence), the "Seen"
  line.
- Rule: a Driver's silence is no sign that it is lost; a second Driver starts only by the restart
  path.
- Where it lives: the [Foreman card](../skills/chantier/references/foreman.md), "Never", and
  [`chantier help host-driver-silence`](../skills/chantier/references/topics/host-driver-silence.md).

## Sessions started over Remote Control (2026-11-20)

- What happened: [Classes of session](proofs/claude-code.md#other-classes-of-session), "The rule:
  starting a session from Remote Control".
- Rule: from Remote Control, start a session with no `cwd` and no `preset`: it lands in the
  steering session's own folder.
- Where it lives: [`chantier help host-remote`](../skills/chantier/references/topics/host-remote.md).

## A stack rebase refused with no rebase rule set (2026-11-23)

- What happened: [Auto mode](proofs/claude-code.md#auto-mode), the 2026-11-23 entry.
- Rule: preflight's P10 names the rebase rules, and a Driver's prompt carries a `Rewrites:` line
  that names the rebase and the push it may run.
- Where it lives: [`chantier help host-auto-mode`](../skills/chantier/references/topics/host-auto-mode.md)
  and the Driver's brief, which `chantier brief` writes.
