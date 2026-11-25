# A hand-back that says its long gate is waived

- `long gate waived (O-<k>)` is checked against the recorded order (`status` lists it; `order waive`), not the rules: it holds when the order is there and its scope fits (`validated by CR-<top>'s gate`, or `follow-up <folder>`). The ask then carries `long gate waived: validated by CR-<top>` or `long gate waived: follow-up <folder>`. No such order: `take <cr> --note "long gate: no waiver recorded for this CR"`, no ask. A brief carries of a waiver only what `take` prints (`gate:`).
- A waiver waives the local run only when its words name that gate (`status`'s `O-<k> waive <cr> <note>`, or the CR's `STATUS.json` `gate.waiver`); else `help local-gate`.
