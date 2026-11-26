# Copilot: the heartbeat

The Chief of Staff arms it (unproved). On the Foreman's `ready <batch>` it sends the Foreman chat
`/every <steering wake> chantier status --refresh --batch <batch> --epoch <n>`, the wake read from
the batch's `timing: Copilot <family> models:` line for the model it started the Foreman with,
else `timing: Copilot other models:`, in `/every`'s form (`4m` by default; the CLI refuses a
Copilot duration that is not whole minutes). The Foreman cannot end `/every`. In direct mode the
Chief of Staff runs the same `/every` in its own session, from its first `take`; on a batch born
paused with no CR it arms it with the first order it sends the Foreman.

At every pause, the automatic one included, tell the user to delete the `/every` in the Foreman
chat (in direct mode, in the Chief of Staff's session). The Foreman also ends its heartbeat on the
first wake that sees no Driver run for 30 minutes or more; the Chief of Staff then tells the user
to delete the `/every` and arms it again with the next order. Whoever ends it first records it with
`chantier status --stop-heartbeat --batch <batch> --epoch <n>` (`pause` already does); while an
`/every` still fires, its next wake clears the mark, which is true.

[Trials](../../../../docs/proofs/copilot.md#heartbeat)
