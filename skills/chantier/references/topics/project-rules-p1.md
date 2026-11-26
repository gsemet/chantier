# The project at a session's start (part 1 of 2)

`$CHANTIER rules` at each session's start; the project's `AGENTS.md` (else `CLAUDE.md` or `.github/copilot-instructions.md`) and what it links say how it builds, tests, ships, merges and releases, on which branch, and the extra review steps. Once per session, at your first turn, run `$CHANTIER preflight` and P9's check (step 1 of starting a batch); tell the user only what P5, P9 and P10 say (the other conditions are a batch's), in one message; a P10 warn is a question, asked once per session. A missing tool is said with what to install. Nothing blocks the user's request there.
- No long gate written down: a question to the user with your recommended answer and an offer to write it in `AGENTS.md`; an absent gate never means success.
- Rules saying there is no long gate, or exempting a kind of CR, or naming a pipeline job as the long gate: a Driver's `handback --no-gate` carries that rule and the steering session checks it.
- A brief (any prompt or message to an agent) states a past fact only with its source: a CR note, a file in the CR's folder or an event in `events.jsonl`; a fact with no source is said as unknown.
