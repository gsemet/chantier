# Claude Code: what the host says of a subagent

All proved in use unless marked.

- **Resume a stopped subagent:** `SendMessage` to its agent id resumes it with its context. Not
  for one the host stopped (`task_status` `killed`, notice `Task "<name>" (<id>) was stopped.`):
  `SendMessage` then gets `Agent <id> was stopped and won't be resumed. Treat its work as
  cancelled; only launch a new agent if the user explicitly asks.`
- **A subagent's turn ends with nothing running in the background:** the host asks its hand-back
  at once (`[handback-send-enforce] Your report has not been delivered. Call SubagentHandback...`);
  a background shell's end wakes it (the CI wait).
- **A background subagent stops:** `Agent "<name>" is waiting on its own background work` means it
  has not ended (it resumes when that work reports); `Agent "<name>" finished` means no live
  background child, and its `SubagentHandback` report arrives as a message.
- **Stopped from outside:** chantier detects only the stop a compaction snapshot reports (the
  steering transcript's `attachment` record `task_status` `killed` with the agent's id as
  `taskId`) and a message to it refused. Unproved: what a stop made by the user in the app leaves
  in the transcript (trial: stop one in the app, read the transcript before and after a
  compaction).
