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

The file's other keys are `prices`, `board` (where [the remote board](boards.md#the-remote-board) listens: `host`
and `port`) and `ci` (`beside_gate: true`: a CR's CI runs while its local long gate runs; it spends CI
minutes on every approved round, off by default). Only the `chantier` CLI reads this file: it refuses an unknown role, key or model, and an
incomplete price entry, with the line, and turns a model name into an exact identifier
(`chantier playbook` shows the result); the agents pass it as printed. A host that cannot set a
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
| Coder, Investigator, Debugger, Conflict resolver, Demo explorer | Sonnet 5.5 | GPT-5.6 Luna |
| Inspector, Verifier | Sonnet 5.5 | GPT-6.1 Sol |
| Spec-writer | Opus 5.5 | Claude Opus 5.5 |

By default every role but the Spec-writer runs Sonnet 5.5 on Claude Code. The roles that judge
keep cards with goals and boundaries, not procedures. On a named trouble a task goes to a new
agent on the escalation model (Opus 5.5 by default), and the report says so. On Copilot the models
are its agent files' models.

**No fallback:** if a host refuses a model, a tool or an agent, chantier stops and says so; it
never picks a look-alike or a workaround.
