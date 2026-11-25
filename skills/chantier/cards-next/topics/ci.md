# CI

While CI runs, do everything that needs no result first: `pr-body.md` and the description as far as they go, the archive's `delivery.md` when `take` printed an archive path, your notes. Then one long wait: start the forge's watch (`gh pr checks <pr> --watch`, `glab ci status --live`) as one command in a background shell, run `lease <unit> hold --lease <n>`, end your turn (`$CHANTIER host end-turn-background`), and let the command's end wake you; no look in between. A Monitor tool used from a subagent is unproved; use the background shell.
- The only source: a claim about CI (running, green, red or none) comes from the forge's list of checks for the PR at the pushed head (`gh pr checks <pr>`, `glab ci list`). The project's files, its rules, an earlier Driver's note and a guess are no source.
- The head first: confirm the PR's head on the forge is the head you pushed (`gh pr view <pr> --json headRefOid`). Checks for an older commit prove nothing.
- Judge by the project's rules: a skipped job is never green; a job also red on the default branch is not the CR's (note it); an infrastructure failure or a flake: `help trouble`; the rest is a round, with a `debugger` first when the cause is not plain.
- The note names the command and the head: `CI: gh pr checks 12 at abc1234: test pass`. The body's CI box says the same, in the template's words.
- A failure is never taken whole: `gh run view <run> --log-failed > <work folder>/ci-<run>.log`, then Grep or Read with an offset, or give it to a `debugger`.
- A stack driver's "PR" is its pushed branch's, the stack's top.
