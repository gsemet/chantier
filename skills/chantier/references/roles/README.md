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

No role has a fixed model in its card. `$CHANTIER models` resolves each role to one exact model id of
the host: the skill's base list (`../models/claude.yml`, `../models/copilot.yml`), then the
user's `~/.config/chantier/models.yml`, then the project's `.agents/chantier.models.yml`. `$CHANTIER setup`
pins that id in each agent file. The Chief of Staff may set a model per role or per CR at the
grill, in the brief's **Models** line; the Foreman or Driver passes what `$CHANTIER models get`
prints for that spawn. Nothing escalates on its own. The reasoning effort works the same way,
from the `effort` section of those files: unset means the user's own setting. A role's tools
are fixed by the skill per host (`tools` section), never by an override. See
[../capabilities/models.md](../capabilities/models.md).

## Every card has

- **Mission**: one sentence.
- **Inputs** and **output**: what it reads, what it leaves behind, and where.
- **Never**: the non-obvious limits.
- **Capabilities**: the files of [../capabilities/](../capabilities/) it reads, and only those.
- **Model**: the role's entry in `$CHANTIER models` (model and effort).

The principles every role follows are in [../principles.md](../principles.md).
