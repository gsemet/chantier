# A stack batch

A stack batch (`status` shows `shape stack`, by `--mode stack` or `order mode --note stack`). Until the first stack is made it runs like a parallel batch with chains, with one limit: a CR handed back `ready` on the default branch asks `ready-to-merge` alone only while no other CR of the stack's chain has an open PR and no stacked CR is open (the shape line's `alone asks`); otherwise it waits for the stack. A merge then goes by the rebase notes (`help stack-merge`); a CR based on another CR's branch hands back `PR in draft`. When nothing of a stack remains open, the batch is as before its first stack: the next one forms at the first take (`next take stack`).
- While another CR of the stack has an open PR, or a stacked CR is open, a CR's readiness reaches the Chief of Staff only through the stack: `judge` prints `no ask:` with the stack's pairs, and at the stack driver's hand-back the `stack-ready-to-merge` ask. A CR truly alone, a fix and a held CR may still ask alone, with no `--outside-stack`.
- The heartbeat's `shape stack: …` line is the stack's reminder, not its rule.
The other asks: `help stack-outside`.
