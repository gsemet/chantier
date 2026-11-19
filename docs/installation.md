# Install

chantier is a [Claude Code plugin](https://code.claude.com/docs/en/plugins), a GitHub Copilot
plugin and an [Agent Plugin](https://agent-plugins.org/): one skill and one agent per role and
host. Claude Code and Copilot get different agents: their tools and model fields differ.

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

New to chantier? Follow the [step-by-step tutorial for Claude Code](tutorials/claude-code.md),
then browse the [use cases](how-to/use-cases.md), with one page per configuration:
[Foreman mode](how-to/use-cases-foreman.md) and [direct mode](how-to/use-cases-direct.md). To plan
outside your project's repository, see [planning modes](explanation/planning-modes.md).

Then restart the session and type one of the entries (on Claude Code, `/chantier:<name>`):
`/chantier` asks Chief of Staff or Griller, `/chief-of-staff` makes it the Chief of Staff, its
mode following the surface (`/chief-of-staff foreman` or `/chief-of-staff direct` to force one),
`/griller` makes it a Griller, a session that
refines the inbox and the backlog while the Chief of Staff runs batches, and `/chantier:status` gives the progress report of the running batch at once, in the same shape as the Chief of Staff's. Besides
the plugin, the only thing to install is [`uv`](https://docs.astral.sh/uv/); as a plugin the CLI runs from the plugin's own folder (`uvx --from`), so
its first run only fetches the CLI's Python packages: it needs the network once, and uv's cache is
enough after that; working on a
repository also needs `git` and the forge's CLI, logged in: `gh` for GitHub, `glab` for GitLab.

Once after installing, open a session on your project and run `/chief-of-staff init` (on Claude
Code, `/chantier:chief-of-staff init`). It checks `uv` and `git`, and the forge's CLI with its
rights and branch rules, and offers to install a missing `gh` or `glab`. On Claude Code it checks
the allow rules and adds the missing ones on your yes, or gives you one command line to run at
your computer. It checks the long gate in `AGENTS.md` and writes the lines on your yes.
