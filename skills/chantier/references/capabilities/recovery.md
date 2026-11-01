# Capability: recovery

## Purpose

Prove the Foreman is alive before reporting progress, and resume only on the user's word.

## Who uses it

Chief of Staff (liveness, resume); Foreman (find orphaned CRs).

## Commands

1. `$CHANTIER foreman get` → session id; `ListAgents` shows it busy or idle. Not listed means down.
2. `SendMessage` to it: `ping: reply with your $CHANTIER status line`. Alive = a reply in about two
   minutes.
3. Foreman: compare `$CHANTIER agents get` with its live agents; a CR marked working without a live
   Driver is orphaned.
4. Orphan processes in a worktree go to `$CHANTIER cancel <cr>`.

## Rules

- Changed files and running processes do not prove an agent is alive.
- Run the check at your cold start, when the user says they restarted, when `$CHANTIER status` shows
  a stale heartbeat, and before reporting progress after a pause.
- **An app restart stops every session.** You cannot start a new Foreman on your own: tell the
  user what you found and ask. On "resume": run [preflight](preflight.md) again; only if every
  condition passes, start a Foreman with the resume brief below.

```text
Resume <batch>. The app restarted and your Drivers stopped. Relaunch in the background the Driver
of each CR still marked working, from its STATE.md and worktree, keeping uncommitted work; stop
orphan processes with $CHANTIER cancel. Then continue the batch.
```

## Failure handling

Preflight fails at resume: print the failure block; start nothing.
