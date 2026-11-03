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
3. **A plugin**: [`plugin.json`](plugin.json) (Agent Plugins 1.0) and
   [`.claude-plugin/`](.claude-plugin/) (Claude Code manifest and marketplace) ship the skill and
   one agent per role in [`agents/`](agents/).

The agents in `agents/` are **generated**: edit the templates in
[`skills/chantier/assets/agents/`](skills/chantier/assets/agents/) or the base model lists in
[`skills/chantier/references/models/`](skills/chantier/references/models/), then run
`just agents`. CI fails if `agents/` is out of date.

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
just check          # agents up to date, CLI unit tests, whole batch scenario: run before any PR
just test -k gate   # CLI unit tests, with pytest arguments
just scenario       # one whole batch, end to end, through the real CLI and a fake gh; no model
just agents         # regenerate agents/ after editing a template or a base model list
```

- Repository text is in English.
- Write code and docs in the style of the surrounding files: short sentences, exact terms.
- A change to the CLI comes with a unit test; a change to the batch flow, with a scenario check.
- CI runs `just check` on Linux, macOS and Windows for every pull request.

## Versions

One version, `MAJOR.MINOR.PATCH`, is carried by the CLI, `pyproject.toml`, `uv.lock`,
`SKILL.md`, the three manifests, the agent templates and the generated agents. Never edit it by
hand:

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

Users get the new version with `claude plugin marketplace update chantier`, then a restart of
their session. A user who installed agent files for a model override (`chantier setup`) must run
it again: preflight reports those files as an old template until then.
