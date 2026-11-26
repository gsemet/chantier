# A parked CR: back, dropped

- Back (`note <cr> wait cleared: ...`, or `status` shows `parked: <cr> wait cleared`): `take <cr> --note "wait cleared: <what>" --epoch <n>`, a new Driver, before any queued CR, no round. In a stack it joins as a working CR.
- Dropping a parked or held CR with dependents (`order drop` names them): in a stack `take stack --note "drop: <cr> to <destination>"`; else each dependent with a Driver or a branch gets `rebase: <cr> dropped` (a plain `status` first: `working`, `[foreman→driver <dep>] note rebase: <cr> dropped`; `ready` or `blocked`, `take <dep> --note "rebase: <cr> dropped"`); a queued one needs none.
- A batch left with only parked or blocked CRs is blocked, not finished: the heartbeat ends as usual (`help wakes`), and a cleared wait's order line wakes you.
