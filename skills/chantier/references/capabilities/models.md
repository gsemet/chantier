# Capability: models

## Purpose

Run every role on the exact model and reasoning effort the configuration names, and never on a
look-alike.

## Who uses it

Chief of Staff (the brief's **Models** line), Foreman and every Driver (each spawn).

## Commands

```bash
$CHANTIER models                        # the resolved model (and [effort]) of each role for this host
$CHANTIER models check                  # config and brief valid; exit 2 otherwise
$CHANTIER models get <role> [--cr CR-n] # what to pass as `model` and `effort` for one spawn
$CHANTIER models audit [--session <id>] # Copilot: the model and effort each spawn really ran; exit 2
                                   # on a mismatch
```

Sources, later wins: the skill's base list (`references/models/claude.yml`,
`references/models/copilot.yml`), the user's `~/.config/chantier/models.yml`, the project's
`.agents/chantier.models.yml`, then the brief's **Models** line. User and project files use the same
sections under a host key:

```yaml
copilot:
  roles:
    coder: gpt-5.6-terra
  catalog:              # add an id the base list does not know yet
    gpt-7-luna: GPT-7 Luna
  aliases:              # optional short names, resolved by the CLI only
    luna: gpt-5.6-luna
  effort:               # low, medium, high, xhigh, max, or inherit; unset = the user's setting
    coder: low
    inspector: high
```

`heartbeat: <n>m` (60 s to 60 min) sets the Foreman's wake interval per host; keep it under
the prompt-cache TTL of the host's Claude models (base list: `55m` Claude Code, `4m` Copilot).

`tools` is a base-list section only: a role's tools are part of its contract, so an override
that sets `tools` fails `$CHANTIER models check`.

### Which agent a role runs

The plugin ships one agent per role and host, built from the base list: `chantier:<role>` on
Claude Code (`agents/`), `<role>` on Copilot (`com.github.copilot/agents/`). Nothing is
installed in the repository. Each role runs, in this order:

1. **The repository's own agent**, named in its `AGENTS.md`, one line per role:

   ```markdown
   - chantier debugger agent: .github/agents/my-debugger.agent.md
   - chantier coder agent: .claude/agents/rust-coder.md
   ```

   The file must be where the host loads agents from (`.claude/agents/`, `.github/agents/`), and
   it decides its own model, effort and tools. When the user asks to customize a role, the Chief
   of Staff adds that line (and, if asked, writes the agent file); then a restart of the session.
2. **A file `$CHANTIER setup` installed** (`.claude/agents/<role>.md`, `.github/agents/<role>.agent.md`):
   only without the plugin, a skill installed on its own.
3. **The plugin's agent.**

`$CHANTIER models get <role>` prints the agent in its `agent:` line.

A model in `models.yml` or the brief that differs from the plugin's agent is passed at the spawn
on Claude Code (aliases). Copilot refuses it (`model-policy: required`), and an effort cannot be
passed at a spawn on either host: for those, `$CHANTIER models check` fails and says to point the
role to the repository's own agent in `AGENTS.md`.

`$CHANTIER setup` (without the plugin) writes each host's own frontmatter:

| | Claude Code (`.claude/agents/`) | Copilot (`.github/agents/`) |
|---|---|---|
| Model | `model: <id>` | `model: [<display>, <id>]` and `model-policy: required` |
| Effort, when set | `effort: <level>` | `reasoning-effort: <level>` |
| Tools | `tools: Bash, Read, …` | `tools: ["execute", "read", …]` and `strict-tools-list: true` |

With `model-policy: required`, Copilot refuses a spawn whose model (or effort) it cannot honor
instead of falling back to the session's model, and refuses a per-spawn model override. So on
Copilot the brief's **Models** line may change only roles left on `inherit` and the Foreman;
`$CHANTIER models check` fails on any other entry. Point the role to the repository's own agent
in `AGENTS.md` instead, then restart the session.

The brief's **Models** line holds `role=id` or `role@CR-n=id` entries, for example
`- Models: coder@CR-102=gpt-6.1-sol, inspector=kimi-k3` (valid on Claude Code, or on Copilot
for roles left on `inherit`).

## Rules

- **A model name is an opaque id.** Write it, pass it and compare it character for character.
  Never shorten, re-case, re-space or "correct" it; never map a name to the one that looks
  closest (`gpt-5.6-luna` is not `gpt-6-luna`).
- **Spawn with what `$CHANTIER models get` prints.** `agent: <agent>`: the agent to spawn,
  exactly. `model: omit (…)`: pass no `model`; the agent file pins it. `model: <id> (…)`: pass
  `<id>` exactly. Nothing else picks a model.
- **Never pass an effort to a role's spawn.** A per-spawn `effort` / `reasoning_effort` would
  override the agent file. `effort: <level>` is printed only for the Foreman on Claude, whose session `start_session` starts
  with that level; `effort: omit (…)` means pass none. On Copilot the Foreman's agent file holds
  its effort, but `create_session` cannot apply it: the audit reports it as a NOTE, not a mismatch.
- **The user's words become an id only through the catalog.** At the grill, if the user names a
  model that `$CHANTIER models` does not list exactly, ask which id they mean; do not guess.
- **A refused model is a stop.** If the host refuses or replaces the model, the spawn is
  `blocked` with the host's exact text; never retry on another model.
- With the plugin, there is nothing to set up. Without it, after a config change: `$CHANTIER
  setup`, then restart the session (`$CHANTIER preflight` P4 fails while agent files differ from
  the config).

## Failure handling

- `$CHANTIER models check` or `get` exits 2: start nothing; show its lines to the user.
- `$CHANTIER models audit` reports a mismatch: stop spawning for that role and tell the Chief of Staff
  with the line it printed.
