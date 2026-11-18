# What you say

Talk to the Chief of Staff in plain language. Each phrase below, or one close to it, does what its row says.

| You say | What happens |
| --- | --- |
| "init", "I am new here" | the five stage folders are created, then a guided tour of how your project works with chantier, and the checks of your machine, each missing piece asked and fixed |
| "become chief of staff" (`/chief-of-staff`) | this session takes the seat: the one session that opens and runs batches in the repository |
| "you are a griller" (`/griller`) | this session refines the inbox and the backlog, never opens a batch; the Chief of Staff picks up what it files |
| "status?" (`/chantier:status`) | the progress report: the table of CRs, their state, their PR and the cost; it changes nothing |
| "chantier reload" (`/chantier:chantier reload`, `/chantier:chief-of-staff reload`, `/chantier:griller reload`) | the session reads chantier's rules again, typically after a compaction; on Claude Code the plugin also tells the session, at every compaction, to call its role skill again with `reload` |
| "file this idea" | a CR folder in the inbox; it can be refined at any stage |
| "make it a P2" | it moves into the prioritized backlog |
| "it is grilled enough" | the spec-writer writes the Change Specification in the background; on an impactful CR the spec critic checks it after |
| "run the P1s", "run these in series", "build a stack of these" | preflight, questions, the plan, then a Foreman starts on your go, or the Chief of Staff steers in direct mode, as the plan says (the surface, or your `foreman` / `direct`); a stack is one native stack on the forge, merged in one action from its top PR or one PR at a time from the bottom, as you choose; a PR ready to merge (out of draft) is mergeable at once, a PR in draft is not |
| "status?" | one line per CR with its PR; a blocked CR comes back as a question |
| "drop CR-103", "I merged #42" | an order for the steering session (the Foreman, or the Chief of Staff in direct mode), never a direct action on a Driver |
| "close the batch" | the check and the final cost, then closing on your yes |
| "release v1.4.0" | a release CR, run by your project's procedure; you approve each irreversible action |
| "what did it cost?" | measured cost: the Foreman, each Driver type, each worker type, and why |
| "use my `rust-coder` agent as the coder" | that role runs your agent from the next batch |
| "add a security review with `sec-reviewer`" | a new review step the Driver runs after the Inspector |
| "our long gate is `npm test`" | the Chief of Staff proposes the exact `AGENTS.md` lines and writes them on your yes (see [Your gates](../how-to/gates.md)) |
| "which agents and models?" | the team: each role, its agent, its model (`chantier playbook`) |
| "run the inspector on Opus" | a `model` for the role under `hosts.<host>.roles` in `chantier.yaml`, which the CLI resolves to the exact model (or refuses an unknown or ambiguous name) |
