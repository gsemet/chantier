# The production team

One card per role. A card holds only what a capable model would not do on its own from the
role's intent: the host's mechanics, who owns what, and the batch's invariants. General
engineering practice is left to the model.

| Role | Runs as | Owner | Card |
| --- | --- | --- | --- |
| Chief of Staff | the user's Desktop session | the user | [chief-of-staff](chief-of-staff.md) |
| Foreman | nested, detached Desktop session | Chief of Staff (starts it once) | [foreman](foreman.md) |
| CR Driver | `cr-driver` agent, background | Foreman | [cr-driver](cr-driver.md) |
| Stack driver | `stack-driver` agent, background | Foreman | [stack-driver](stack-driver.md) |
| QA driver | `qa-driver` agent, background | Foreman | [qa-driver](qa-driver.md) |
| Investigator | `investigator` agent, foreground | a Driver | [investigator](investigator.md) |
| Coder | `coder` agent, foreground | a Driver | [coder](coder.md) |
| Inspector | `inspector` agent, foreground | a Driver | [inspector](inspector.md) |
| Debugger | `debugger` agent, foreground | a Driver | [debugger](debugger.md) |
| Verifier | `verifier` agent, foreground | a Driver | [verifier](verifier.md) |
| Conflict resolver | `conflict-resolver` agent, foreground | a Driver or the stack driver | [conflict-resolver](conflict-resolver.md) |

## Model and effort

The static Claude and Copilot agent files declare their own model, effort and tools. A project
can copy and edit an agent for its host, optionally selecting a differently named copy in
`AGENTS.md`. The Foreman or Driver follows `$CHANTIER models get` for each spawn; nothing
escalates on its own. Foreman nested-session tools are supplied by the host rather than the
worker-agent file. See [../capabilities/models.md](../capabilities/models.md).

## Every card has

- **Mission**: one sentence.
- **Inputs** and **output**: what it reads, what it leaves behind, and where.
- **Never**: the non-obvious limits.
- **Capabilities**: the files of [../capabilities/](../capabilities/) it reads, and only those.
- **Model**: the role's entry in `$CHANTIER models` (model and effort).

The principles every role follows are in [../principles.md](../principles.md).
