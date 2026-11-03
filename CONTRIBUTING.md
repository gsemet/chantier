# Contributing to chantier

This guide is for the people who work on chantier itself. To use it, read the
[README](README.md).

## How the project is built

chantier is three things in one repository:

1. **A skill** ([`skills/chantier/`](skills/chantier/)). `SKILL.md` is the Chief of Staff's entry
   point. [`references/`](skills/chantier/references/) holds one file per running context:
   `concepts.md` (read by everyone), `chief-of-staff.md`, `foreman.md`, `driver.md`, `worker.md`
   and `message-formats.md`. They are written for agents: short, exact, one meaning per word.
2. **A CLI** ([`skills/chantier/scripts/cli/`](skills/chantier/scripts/cli/)): plain Python with
   no dependency, run by `uv run --script`, on Linux, macOS and Windows. It owns every mechanical
   step and writes only in the target repository's `.agents/changes/`, as plain JSON and
   Markdown: `backlog/` (the CR folders, each with a `work/` folder while it runs) and
   `batches/<batch>/` (`batch.json`, `events.jsonl`, the brief and the report). There is no
   configuration file: the Chief of Staff reads the project's `AGENTS.md` and passes the gates,
   the branch and the team to `chantier open`, which records them in `batch.json`.
   The CLI is also where a role meets its agent: `chantier spawn <role> <cr>` prints the agent to
   start and the whole prompt, so the role's contract travels with every spawn and a user's own
   agent gets the same one as ours.
3. **A plugin**: [`plugin.json`](plugin.json) (Agent Plugins 1.0),
   [`.claude-plugin/`](.claude-plugin/) and [`.github/plugin/`](.github/plugin/) ship the skill
   and one agent per role and host: [`agents/`](agents/) for Claude Code (`chantier:<role>`),
   [`com.github.copilot/agents/`](com.github.copilot/agents/) for Copilot (`chantier-<role>`, a
   prefix a project agent named after the role cannot shadow). An agent file holds only its
   host's frontmatter (model, tools) and a short body; both hosts' bodies are identical, which the
   tests check. The Foreman is a session, not an agent: its model is in
   [`roles.py`](skills/chantier/scripts/cli/src/chantier/roles.py).

The design rule that shapes everything: **fail, never improvise.** When a tool, a host feature,
a model or an agent is not exactly available, chantier stops and says so; it never picks a
look-alike. Keep that true in any change.

## Set up

Install [`uv`](https://docs.astral.sh/uv/), [`just`](https://just.systems/), `git` and `gh`.
Nothing else: `uv` fetches Python and the test dependencies.

To try your working copy in Claude Code, install the plugin from your checkout:

```bash
claude plugin marketplace add ./
```

```bash
claude plugin install chantier@chantier
```

## Daily work

```bash
just                # list the recipes
just check          # structure tests: run before any PR
just test -k roles  # structure tests, with pytest arguments
just scenario       # one whole batch, end to end, through the real CLI and a fake gh, then glab
```

- Repository text is in English.
- Write code and docs in the style of the surrounding files: short sentences, exact terms.
- Tests check the structure (versions, manifests, agents, references, and a smoke run in a fresh
  repository) in a few seconds. They do not evaluate the batch workflow: run `just scenario`
  ([scenario/](scenario/README.md)) when you change it.
- With real agents, the [eval campaigns](evals/README.md): `claude-smoke` after a change to a
  role or the flow, `claude-full` before a release, `copilot` for a change to Copilot's
  mechanics. Each run commits its report.
- `main` is protected: every change goes through a pull request, merged by rebase once CI
  (`just check` on Linux, macOS and Windows) is green.

## Versions

One version, `MAJOR.MINOR.PATCH`, is carried by the CLI, `pyproject.toml`, `uv.lock`,
`SKILL.md`, the plugin manifests and marketplaces, and the agents. Never edit it by hand:

```bash
just version-show
just version 1.2.3            # an exact version
just bump-version             # patch; or `just bump-version minor`, `just bump-version major`
```

The script writes nothing if one file disagrees with the current version. Preflight refuses to
run when the skill, the CLI and the agents disagree, so every file must move together.

## Release

1. From an up-to-date `main` with green CI, on a new branch, prepare the release. This bumps
   the version, runs `just check` and commits `release: vX.Y.Z`; it pushes nothing:

   ```bash
   just release          # patch; or `just release minor`, `just release major`
   ```

2. Push the branch, open a pull request and merge it by rebase once CI is green.
3. Tag the merged commit on `main` and push the tag:

   ```bash
   just tag
   ```

4. Publish the GitHub release with its notes:

   ```bash
   gh release create vX.Y.Z --generate-notes
   ```

Users get the new version by updating the plugin from its marketplace, then restarting their
session.
