# The project at a session's start

`$CHANTIER rules` at each session's start; the project's `AGENTS.md` (else `CLAUDE.md` or `.github/copilot-instructions.md`) and what it links say how it builds, tests, ships, merges and releases. Once per session run `$CHANTIER preflight` and P9; tell the user only what P5, P9 and P10 say.
- No long gate written down: a question to the user with your recommended answer and an offer to write it in `AGENTS.md`; an absent gate never means success.
- A long gate in the project's rules while `playbook` prints `long gate: none named in chantier.yaml`: ask, with the exact lines proposed (a name and the rules' command), written on the user's yes in the main checkout's root `chantier.yaml`, uncommitted, with an offer of an inbox CR that commits it; until it merges, a PR changing that file stops the fast-forward after a merge, which reports it and overwrites nothing. A `playbook` line saying a surface's `long_gate.commands` is ignored: same offer.
- "Our long gate is `<command>`": propose the `AGENTS.md` line naming it and the `chantier.yaml` entry holding the command; ask once whether it is isolated per worktree and propose `long_gate.parallel` when absent.
- Rules saying there is no long gate, or exempting a kind of CR, or naming a pipeline job as the long gate: a Driver's `handback --no-gate` carries it and the steering session checks it.
- A brief states a past fact only with its source.
