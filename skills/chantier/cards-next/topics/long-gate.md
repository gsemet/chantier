# A hand-back with no long gate

A hand-back `no long gate: <reason>` (`handback --no-gate`) is checked first against `$CHANTIER rules`; `judge` then words the ask `… no long gate: <reason>`.
- It holds when the rules say the project has no long gate, exempt this CR (by kind of change such as docs only: read the changed files, `gh pr diff --name-only`, `glab mr diff`), or name a pipeline job as the long gate and that job is green at the PR's head (`gh pr checks <pr>`; `glab ci status --branch <branch>`, unproved). Not green: `take <cr> --note "long gate: <job> not green at <sha7>"`, no ask.
- The rules declare a long gate that covers the CR: `take <cr> --note "long gate: <why the exemption does not hold>"`, no ask.
- The rules say nothing: `$CHANTIER asks "question <cr> no long gate written down: <the Driver's reason>"`.
- A critical-path CR whose gate is queued (`gate queued behind …`), or the CR the user says they merge next in a parallel batch: `gate <cr> --first --epoch <n>`, and say in your next report which CR, ahead of which. Never for another reason, nor at a Driver's request alone.
A waiver: `help long-gate-waiver`.
