# Your own agents and models

How to run your own agents in a role, which model each role runs, and the no-fallback rule.

## Your own agents

Any role can run one of your agents, with a model of your choice and the skills it needs. Tell
the Chief of Staff, and it writes them in an optional `chantier.yaml` at your project's root,
shared with your team (with none, every role runs the plugin's agent):

```yaml
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

The file's other keys are `prices`, `board` (where [the web board](web-board.md) listens: `host`
and `port`), `ci` (`beside_gate: true`: a CR's CI runs while its local long gate runs; it spends CI
minutes on every approved round, off by default) and `long_gate` (how many long gates may run at once, [your gates](gates.md)). Only the `chantier` CLI reads this file: it refuses an unknown role, key or model, and an
incomplete price entry, with the line, and turns a model name into an exact identifier
(`chantier playbook` shows the result); the agents pass it as printed. On Copilot the names it
knows are GitHub's own tables (`github/docs`, refreshed by `just copilot-models`): the identifier is
the display name with each footnote marker (`[^...]`) and `(preview)` dropped, every other
parenthetical kept, in lower case, each run of spaces made one `-`, dots kept, ends trimmed. An
identifier the CLI reference does not list is derived by that rule, unproved until `listModels()`
(for example `claude-opus-4.8-(fast-mode)`, likely not what Copilot takes,
[copilot-session-usage#67](https://github.com/gsemet/copilot-session-usage/issues/67)). A short
name such as `opus` can match several Copilot models and is then refused as ambiguous, with the
matching identifiers: write the identifier. A host that cannot set a
model when it starts an agent refuses a
`model`. A required skill the Chief of Staff's session lacks is warned about, and the role works
without it. The role's contract is its card in the skill, so your agent only needs the tools the
role uses. Extra review steps stay in a `chantier` section of your `AGENTS.md`:

```markdown
## chantier

- security-review: `sec-reviewer`, after the Inspector: OWASP top 10 on the diff
```

A name that is not a built-in role becomes an extra review step: it runs after the Inspector
approves and answers with the same verdict. A running batch keeps the team it started with.

## Models

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

By default every role but the Spec-writer and the Spec critic runs Sonnet 5.5 on Claude Code. The roles that judge
keep cards with goals and boundaries, not procedures. On a named trouble a task goes to a new
agent on the escalation model (Opus 5.5 by default), and the report says so. On Copilot the models
are its agent files' models: they set `model-policy: required`, so the file's model wins over a model
passed at the start
([CLI command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#command-line-options));
seen in the Copilot App in CR-296 (a Coder started with GPT-6.1 Sol ran on its file's GPT-5.6
Luna).

**No fallback:** if a host refuses a model, a tool or an agent, chantier stops and says so; it
never picks a look-alike or a workaround.
