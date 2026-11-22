# Your own agents and models

How to run your own agents in a role, which model each role runs, and the no-fallback rule.

## Your own agents

Any role can run one of your agents, with a model of your choice and the skills it needs. Tell
the Chief of Staff, and it writes them in an optional `chantier.yaml` at your project's root,
shared with your team (with none, every role runs the plugin's agent). Every role setting is per
host: it goes under `hosts: claude: roles:` or `hosts: copilot: roles:`, never for all hosts:

```yaml
hosts:
  claude:
    roles:
      coder:
        agent: rust-coder
        model: opus
        skills: [jira]
      cr-driver:
        agent: my-driver
prices:                    # a model chantier has no price for yet, in $/MTok
  claude-example-6-0:
    input: 3
    cache_write_5m: 3.75
    cache_write_1h: 6
    cache_read: 0.30
    output: 15
```

### The layers

The configuration is read in four layers, weakest to strongest, and merged node by node:

| Layer | File | When |
| --- | --- | --- |
| defaults | `config/chantier.defaults.yml` in the plugin (never edit it: a release changes it) | always |
| surface | `chantier.yaml` at the [planning surface](planning-modes.md)'s root, for all its projects | external planning surface |
| surface project | `projects/<name>/chantier.yaml` in the surface | external planning surface |
| repository | `chantier.yaml` at the code repository's root | always |

Each file may be `chantier.yaml` or `chantier.yml`, never both in one place (refused, with both
paths). A layer carries only what it changes: a mapping merges key by key with the layers below, a
value (a scalar, or a list such as `skills`) replaces the weaker one whole, and a `prices` entry is
replaced whole. For example, the surface root sets the Coder's `model: opus` for every project, and
one project's code repository sets `model: sonnet`: that project runs Sonnet, the others Opus.

A stronger layer takes a weaker value back by writing `default` (`~` and `null` read the same) as
the value. The surface root names `agent: my-coder`, one project's `chantier.yaml` writes
`agent: default`, and that project runs the plugin's Coder. `model: default` brings back the
shipped model, and `prices: <id>: default`, `board: default`, `ci: default`, `long_gate: default`
and `hosts: copilot: roles: coder: default` do the same for what they name; so does a timing
setting's `default` (`hosts: claude: timing: session: cache_ttl: default`, or `timing: default`
for the whole block), which brings back the shipped value. No model and no agent
can be named `default` (a quoted `"default"` is refused), and an empty value (`agent:` with nothing
after it) is not a reset: it is refused. `chantier playbook` prints each value with its layer in
brackets, and `[reset in <layer>]` for a value taken back. A top-level `roles` key is refused in
every layer: move it under `hosts.<host>.roles`.

`escalation` names the model a new agent of that role starts on after a named trouble.
Only `coder`, `debugger` and `conflict-resolver` carry one.
`skills` and `tools` list what the role needs, which preflight checks; they restrict nothing.

### How a role starts

A role starts one of four ways, from its `agent` and `model` (a model equal to the role's default
counts as none):

| You set | Claude Code | Copilot |
| --- | --- | --- |
| nothing | the plugin's agent, its file's model | the same |
| `agent` only | your agent, its file's model | the same |
| `model` only | the plugin's agent, with that model, its own tools | a generic agent with the role's contract in its prompt and that model |
| `agent` and `model` | your agent, with that model | refused, with the reason: name the model in your agent's own file |

A generic agent has the caller's tools, not restricted (`chantier playbook` says so); a role's tools
change only by naming your own agent. Copilot starts a named agent with a model only once its eval
probe shows it does (`evals/copilot/RUNBOOK.md`, "Models"). A Spec-writer or Spec critic started
generic, or as your own agent, is counted with the Chief of Staff's steering, not on the grill line
of `chantier cost` (`cost --explain` says so).

### The file's keys

`hosts.<host>.timing` sets three settings: `steering_wake` (how often the Foreman, or the Chief of
Staff in direct mode, wakes to refresh the status), `cache_ttl` (how long the host's prompt cache
keeps a prefix; the CLI warns when a wake is longer than it, as each wake then starts cold) and
`ci_reruns` (how many times a Driver re-runs a CI job that failed on the infrastructure, 0 or
more). Durations are `<n>s`, `<n>m` or `<n>h`, at least one minute. Written directly under
`timing:`, a setting is the general value; under a column it is that column's. Claude Code's
columns are `subagent` (a Driver: reads `cache_ttl` and `ci_reruns`) and `session` (the Foreman or
the Chief of Staff: reads `steering_wake` and `cache_ttl`); Copilot's are `claude` and `gpt`, the
model family, each reading all three, and the general value serves every other model. A setting
under a column that does not read it is refused. Bounds: on Claude Code `steering_wake` is at most
60 minutes; on Copilot a duration is whole minutes. The shipped defaults are today's behaviour:
Claude Code `steering_wake` 30m, `cache_ttl` 1h for a session and 5m for a subagent, `ci_reruns` 1;
Copilot `steering_wake` 4m, `cache_ttl` 5m, `ci_reruns` 1. A column's value beats the general one
within a layer, and a stronger layer beats a weaker one, whatever the key. `chantier playbook`
prints the result as `timing:` lines; a running batch keeps the timing it opened with. The
[web board](web-board.md)'s Configuration page has a Timing tab for it.

The file's other keys are `prices`, `board` (where [the web board](web-board.md) listens: `host`
and `port`), `ci` (`beside_gate: true`: a CR's CI runs while its local long gate runs; it spends CI
minutes on every approved round, off by default) and `long_gate` (`parallel`: how many long gates may run at once; `commands`: the long gate's names and their commands, read only from the code repository's root `chantier.yaml`; [your gates](gates.md)). Only the `chantier` CLI reads these files: it refuses an unknown role, key or model, and an
incomplete price entry, with the line, and turns a model name into an exact identifier
(`chantier playbook` shows the result); the agents pass it as printed. On Copilot the names it
knows are GitHub's own tables (`github/docs`, refreshed by `just copilot-models`): the identifier is
the display name with each footnote marker (`[^...]`) and `(preview)` dropped, every other
parenthetical kept, in lower case, each run of spaces made one `-`, dots kept, ends trimmed. An
identifier the CLI reference does not list is derived by that rule, unproved until `listModels()`
(for example `claude-opus-4.8-(fast-mode)`, likely not what Copilot takes,
[copilot-session-usage#67](https://github.com/gsemet/copilot-session-usage/issues/67)). A short
name such as `opus` can match several Copilot models and is then refused as ambiguous, with the
matching identifiers: write the identifier. A required skill the Chief of Staff's session lacks is warned about, and the role works
without it. The role's contract is its card in the skill, so your agent only needs the tools the
role uses. Extra review steps stay in a `chantier` section of your `AGENTS.md`:

```markdown
## chantier

- security-review: `sec-reviewer`, after the Inspector: OWASP top 10 on the diff
```

A name that is not a built-in role becomes an extra review step: it runs after the Inspector
approves and answers with the same verdict. A running batch keeps the team it started with.

## Models

The default model of each role is in the plugin's `config/chantier.defaults.yml`, equal to its
agent file's.

| Role | Claude | Copilot |
| --- | --- | --- |
| Chief of Staff | your session (Opus 5.5 recommended) | your session |
| Foreman | Sonnet 5.5, effort medium | Claude Opus 5.5 |
| Stack and release drivers | Sonnet 5.5 | Claude Opus 5.5 |
| CR driver | Sonnet 5.5 | Claude Sonnet 5.5 |
| QA driver | Sonnet 5.5 | Claude Sonnet 5.5 |
| Coder | Sonnet 5.5 | GPT-6.1 Sol |
| Investigator, Demo explorer | Sonnet 5.5 | GPT-5.6 Luna |
| Inspector | Sonnet 5.5 | GPT-6.1 Sol |
| Verifier, Debugger, Conflict resolver | Sonnet 5.5 | GPT-6.1 Terra |
| Spec-writer | Opus 5.5 | Claude Opus 5.5 |
| Spec critic | Opus 5.5 (Fable on request) | Claude Opus 5.5 |
| Board's Griller | Opus 5.5 | Claude Opus 5.5 |

The board's Griller runs only the plugin's own agent: its model is yours to set, its agent is not (see [the web board](web-board.md#the-boards-griller)).

By default every role but the Spec-writer, the Spec critic and the board's Griller runs Sonnet 5.5 on Claude Code. The roles that judge
keep cards with goals and boundaries, not procedures. On a named trouble a coding task goes to a new
agent on the role's `escalation` model (Opus 5.5 by default, set per role in the configuration),
once per CR and then the user, and the report says so. On Copilot the agent files' models run when no
model is passed; a model you set starts a generic agent until Copilot is proved to start a named
agent with a model (the eval's probe). The agent files set `model-policy: required`, except the
Coder's, which leaves it out for that probe: with the policy, the file's model wins over a model
passed at the start
([CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#command-line-options));
seen in the Copilot App in CR-296 (a Coder started with GPT-6.1 Sol ran on its file's GPT-5.6
Luna).

**No fallback:** if a host refuses a model, a tool or an agent, chantier stops and says so; it
never picks a look-alike or a workaround.
