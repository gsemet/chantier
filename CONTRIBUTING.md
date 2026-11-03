# Contributing to chantier

This guide is for the people who work on chantier itself. To use it, read the
[README](README.md).

## How the project is built

chantier is three things in one repository:

1. **A skill** ([`skills/chantier/`](skills/chantier/)): `SKILL.md` and the `references/` it
   routes to. The Chief of Staff, the Foreman and every worker read these files. They are written
   for agents: short, exact, one meaning per word ([definitions](skills/chantier/references/definitions.md)).
2. **A CLI** ([`skills/chantier/scripts/cli/`](skills/chantier/scripts/cli/)): plain Python with
   no dependency, run by `uv run --script`. It owns every mechanical step and the whole batch
   state (`batch.json`, `events.jsonl`); agents never edit that state by hand. It runs on Linux,
   macOS and Windows.
3. **A plugin**: [`plugin.json`](plugin.json) (Agent Plugins 1.0),
   [`.claude-plugin/`](.claude-plugin/) (Claude Code manifest and marketplace) and
   [`.github/plugin/`](.github/plugin/) (GitHub Copilot marketplace) ship the skill and one agent
   per role and host: [`agents/`](agents/) for Claude Code,
   [`com.github.copilot/agents/`](com.github.copilot/agents/) for Copilot. Their host-specific
   model and tool fields are edited directly; there are no templates or generation step. Every
   spawn carries `skill:` and `changes:` lines, so plugin and project-local copies can find the
   skill and the same batch state. A repository can select its own agent in `AGENTS.md`.

The design rule that shapes everything: **fail, never improvise.** When a tool, a host feature or
a configured model is not exactly available, chantier stops and says so; it never picks a
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
just check          # static-agent and structure tests: run before any PR
just test -k agents # structure tests, with pytest arguments
just scenario       # optional: one whole batch, end to end, through the real CLI and a fake gh
```

- Repository text is in English.
- Write code and docs in the style of the surrounding files: short sentences, exact terms.
- Tests check the structure (versions, manifests, static agents, roles,
  links, and a smoke run in a fresh repository), in a few seconds. They do not evaluate the
  batch workflow: run `just scenario` when you change it.
- CI runs `just check` on Linux, macOS and Windows for every pull request.

## Versions

One version, `MAJOR.MINOR.PATCH`, is carried by the CLI, `pyproject.toml`, `uv.lock`,
`SKILL.md`, the plugin manifests and marketplaces, and the static agents. Never edit it by hand:

```bash
just version-show
just version 1.2.3            # an exact version
just bump-version             # patch; or `just bump-version minor`, `just bump-version major`
```

The script writes nothing if one file disagrees with the current version. Preflight refuses to
run when the skill and the CLI disagree, so every file must move together.

## Release

1. Start from an up-to-date, clean `main` with green CI.
2. Prepare the release. This bumps the version, runs `just check`, commits
   `release: vX.Y.Z` and tags `vX.Y.Z`; it pushes nothing:

   ```bash
   just release          # patch; or `just release minor`, `just release major`
   ```

3. Push the commit and the tag:

   ```bash
   git push --follow-tags
   ```

4. Publish the GitHub release with its notes:

   ```bash
   gh release create vX.Y.Z --generate-notes
   ```

Users get the new version by updating the plugin from its marketplace, then restarting their
session. Project-local agent copies remain the user's responsibility.
