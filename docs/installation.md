# Install

Install chantier as a [Claude Code plugin](https://code.claude.com/docs/en/plugins), a GitHub
Copilot plugin or an [Agent Plugin](https://agent-plugins.org/). It brings one skill and one agent
per role and host. Claude Code and Copilot get different agents: their tools and model fields
differ.

::::{tab-set}

:::{tab-item} Claude Code
```bash
claude plugin marketplace add gsemet/chantier
```

```bash
claude plugin install chantier@chantier
```
:::

:::{tab-item} GitHub Copilot
```bash
copilot plugin marketplace add https://github.com/gsemet/chantier.git
```

```bash
copilot plugin install chantier@chantier
```
:::
::::

Then restart the session. You now have these entries (on Claude Code, type `/chantier:<name>`):

| Entry | What it does |
| --- | --- |
| `/chantier` | asks whether this session is the Chief of Staff or a Griller |
| `/chief-of-staff` | makes this session the Chief of Staff; its mode follows the surface (`/chief-of-staff foreman` or `/chief-of-staff direct` forces one) |
| `/griller` | makes this session a Griller: it refines the inbox and the backlog while the Chief of Staff runs batches |
| `/chantier:status` | gives the progress report of the running batch at once, in the same shape as the Chief of Staff's |

## What else you need

Besides the plugin, install [`uv`](https://docs.astral.sh/uv/). As a plugin, the CLI runs from the
plugin's own folder (`uvx --from`). Its first run fetches the CLI's Python packages, so it needs
the network once; uv's cache is enough after that.

To work on a repository you also need `git` and the forge's CLI, logged in: `gh` for GitHub,
`glab` for GitLab.

## Check your setup

Once after installing, open a session on your project and run `/chief-of-staff init` (on Claude
Code, `/chantier:chief-of-staff init`). It checks `uv`, `git` and the forge's CLI with its rights
and branch rules, and offers to install a missing `gh` or `glab`. On Claude Code it checks the
allow rules and adds the missing ones on your yes, or gives you one command line to run at your
computer. It checks the long gate in `AGENTS.md` and writes the lines on your yes.

Next: follow the [step-by-step tutorial for Claude Code](tutorials/claude-code.md), then browse
the [use cases](how-to/use-cases.md), one page per mode: [Foreman mode](how-to/use-cases-foreman.md)
and [direct mode](how-to/use-cases-direct.md). To plan outside your project's repository, see
[planning modes](explanation/planning-modes.md).
