# Claude Code: the heartbeat

The Foreman (in direct mode the Chief of Staff, in its own session) runs the `/loop` skill in
dynamic mode. The loop's prompt is the command `chantier status --refresh --batch <batch> --epoch
<n>` alone, with no interval in it: a prompt ending in an interval makes `/loop` take its
fixed-interval mode. Each wake is scheduled with `ScheduleWakeup`, the steering wake of the
`timing: Claude Code session:` line of `chantier playbook --batch <batch>`, in seconds, after the
last (3300 seconds by default; the Foreman's own watcher wakes it sooner on a merge, a red CI or a
met wait; the CLI refuses a wake over 60 minutes). A 55-minute wake is **unproved**.

End the heartbeat, never the session, with `ScheduleWakeup` `stop: true`, after `chantier status
--stop-heartbeat --batch <batch> --epoch <n>` (every pause already runs it): right after the pause
(the record alone does not stop the wake, and a later wake's `status --refresh` resets it), and on
the first wake that sees no Driver of any kind run for 30 minutes or more with no order undone. An
order's line or a `ping` starts a turn; if it leaves a Driver running, arm the heartbeat again. On a
batch born paused with no CR, arm the loop only in the turn of the first `take`. No wake ever
arriving is a stop.

[Trials](../../../../docs/proofs/claude-code.md#heartbeat)
