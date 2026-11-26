# --no-gate, waivers and draft PRs

- The steering session checks the rule `--no-gate` quotes and sends the CR back with a note if it does not hold: run the long gate, then hand back again without `--no-gate`.
- A CR whose `take` or `handoff` prints `gate: waived (O-<k>, …)` runs no long gate and hands back with no `--no-gate`: the CLI prints `long gate waived (O-<k>): validated by CR-<top>'s gate` (or `follow-up <folder>`) in the line to send.
- Under a rule that asks a local run (`help conflicts-local-gate`), a waived CR that owes the run still runs `$CHANTIER gate` at its pushed head before its PR leaves draft, unless the waiver's words name that gate: read them in `$CHANTIER status`'s order list (`O-<k> waive <cr> <note>`) or, when cut, in the CR's `STATUS.json` (`gate.waiver`).
- The stack's top, whose `gate:` line says `this CR's long gate validates the stack`, runs its gate as any CR does; a fix its gate finds goes on the top PR or a PR above it.
- A release PR is a draft while its base is not the default branch, and turns ready when the stack driver retargets it and it is green. A project that shows it otherwise (a label, a title prefix, no draft at all) is followed as written. A forge or plan that refuses a draft stops that step: `handback blocked refused <exact text>` (the stack driver: its `anomaly` line).
