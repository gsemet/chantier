# Principles

Only the rules a capable model would not follow on its own here. Each has its reason.

1. **State changes only through `$CHANTIER`.** Several agents write the batch at once; the CLI locks,
   writes atomically and logs the event. A hand edit is lost or corrupts the batch.
2. **Whoever owns a live agent is the only one who stops or messages it.** In Claude Desktop a
   session cannot reach another session's background agents; a message to a busy agent waits for
   its next tool round.
3. **A parent restarts a failing child and never does the child's work.** A parent that codes or
   reviews fills its context and its cache with work it cannot hand over.
4. **A fresh child per round.** A resumed agent keeps a stale picture; the brief and the round
   notes carry everything the next one needs.
5. **The one who checks never wrote it.** The Verifier and the Inspector are new agents; their
   value is that they share none of the Coder's assumptions.
6. **Evidence is the artifact, not a report.** A claim counts when a command run at the pushed
   head shows it. Notes, summaries and green CI are not proof.
7. **Two failed fixes on one premise: test the premise.** A third fix on the same premise usually
   fails the same way.
8. **A red that is red on main is not the CR's.** Fixing main inside a CR hides the fix in the
   wrong PR; report it instead.
9. **Stop on a stale epoch.** Exit 3 means another Foreman runs the batch; two Foremen spawn the
   same CR twice.
10. **Fail, never improvise.** When a precondition fails, a capability is missing (a tool, a
    command, a host feature the skill names) or a model is not available exactly as configured,
    stop: start nothing, return `blocked` and say which one failed, with the error as printed.
    Never substitute another tool, model, mechanism or estimate, even one that looks close. The
    goal is the most reliable and cheapest team: a workaround costs tokens, hides the defect and
    makes the next run unpredictable, while a clear stop costs one question to the user.
11. **Never merge.** The user merges; the batch lands only when every CR is merged or cancelled.
