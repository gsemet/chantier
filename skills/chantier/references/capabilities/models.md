# Capability: models and agents

## Purpose

Use the static agent for each role and host, or the user's project-local copy. Never substitute
a different model or tool when a host refuses one.

## Who uses it

Chief of Staff, Foreman and Drivers.

## Commands

```bash
$CHANTIER models                         # shipped model pins or "custom agent decides"
$CHANTIER models check                   # static agents and any active brief are valid
$CHANTIER models get <role> [--cr CR-n]  # agent to spawn, and what to pass to the host
$CHANTIER models audit [--session <id>]  # Copilot: check actual spawns and heartbeat
```

The plugin ships explicit, hand-maintained files in `agents/` (Claude Code) and
`com.github.copilot/agents/` (Copilot). Their frontmatter declares the host's model, optional
effort and tools. There are no model YAML preferences, batch model overrides, agent templates,
or agent generation. Old preference files are ignored; a nonempty legacy **Models** override in
an active brief is refused.

### Select a project agent

For a role other than the Foreman, resolution is:

1. A host-specific agent named in the project's `AGENTS.md`, for example:

   ```markdown
   - chantier copilot coder agent: .github/agents/my-coder.agent.md
   - chantier claude coder agent: .claude/agents/rust-coder.md
   ```

   An unqualified `- chantier <role> agent: <path>` also works when that file is valid for the
   current host. Paths must be in the host's project agent directory. No role may have two
   applicable mappings.
2. A project-local copy with the role's original filename:
   `.claude/agents/<role>.md` or `.github/agents/<role>.agent.md`.
3. The plugin's static agent: `chantier:<role>` on Claude Code, `<role>` on Copilot.

Copy the file for the host, edit its frontmatter and keep its role instructions. Add the mapping
only when the copy has a different name. The copy chooses its own model, effort and tools; users
add any project-specific tools there. Restart the host session so it discovers the copy.
`$CHANTIER models get <role>` prints the selected `agent:`. Project-local agents are not checked
for plugin version drift or audited against shipped model pins.

The Foreman is a nested session rather than a spawned worker agent. Its model and, on Claude
Desktop, its effort come from the corresponding static or project-local `foreman` file. The
session host supplies the Foreman's tools. Copilot `create_session` cannot select an agent file or
set effort: its session effort and tools apply, even if the Copilot Foreman file lists others.

## Rules

- Treat a model id as opaque: copy it exactly, without guessing or substituting a look-alike.
- Before each worker spawn, run `$CHANTIER models get <role> --cr <cr> --batch <batch>`; spawn the
  named agent and omit model and effort when the command says to omit them.
- Before starting the Foreman's session, use its printed model and, where supported, effort.
  The heartbeat is fixed at `55m` on Claude and `4m` on Copilot.
- A refused model or tool is a stop: report the host's exact text; never retry with another.
- Every session and spawn prompt carries the absolute `skill:` and `changes:` paths
  ([message formats](../message-formats.md)).

## Failure handling

- `$CHANTIER models check` or `get` exits 2: start nothing; show its lines to the user.
- `$CHANTIER models audit` reports a mismatch: stop spawning for that role and tell the Chief of
  Staff. Custom and inherited worker models are reported as unchecked; Copilot Foreman effort
  is reported as a note because `create_session` cannot set it.
