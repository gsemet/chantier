# Contributing to chantier

This guide is for the people who work on chantier itself. To use it, read the
[README](README.md).

## How the project is built

### What is chantier?

You only ever talk to the **Chief of Staff**, in your own session.
It keeps the backlog, asks you the questions a change needs, and starts work only on your go.

1. **It learns your project.** It reads your `AGENTS.md` (or `CLAUDE.md`) for how you build,
   test, ship, merge and release, your default branch and your team, and asks you what it does
   not say. There is nothing else to configure: every agent reads the same file.
2. **You file work.** Each item becomes a **Change Request**: a folder that keeps the raw request
   (`intake/`), its analysis (`01-intent.md`), every answer you give (`02-answers.md`) and the
   self-contained **Change Specification** (`03-change-spec.md`), and, when it needs another CR
   first, a `depends.json` (`{"after": ["<slug>"]}`). After the grill, the Chief of Staff
   restates the CR and asks whether it is grilled enough; on your word a **spec-writer** agent
   writes `03-change-spec.md` in the background, and the Chief of Staff reviews it against your
   answers before showing it to you.
3. **You start a batch** ("run the P1s"; four slots; the CRs run in parallel unless you ask for a [series or a stack](README.md#batch-modes)). After a preflight and your go, the
   Chief of Staff starts one **Foreman** in a nested session. In **direct mode** (used under Remote
   Control, where the host cannot start a Foreman session, or when you force it) no Foreman starts: the Chief of
   Staff steers the batch from its own session, with the same limits, folders and reports, and a
   batch (a CR added while it runs is queued and taken when a slot frees, and a paused batch takes several, the first start setting it running); it may switch to Foreman mode on your word.
   Direct mode is less dynamic than Foreman mode (the Chief
   of Staff, busy steering, holds no grill in that session) but has the same lifecycle: a batch is
   running, then paused, then closed on your word. See [direct mode](docs/use-cases-direct.md).
4. **The Foreman runs the batch.** It starts one background **Driver** per working CR (a slot is a
   running Driver), plus a stack driver and a QA driver, which takes a slot, when needed, and keeps itself warm with a heartbeat.
5. **Each Driver creates the CR's git worktree and branch, then runs short foreground workers**
   in it: Investigator, Coder, Inspector, Debugger, Verifier, Conflict resolver, and any review
   step you added. Then it commits, rebases, pushes, opens the PR and watches its CI itself,
   with `git` and `gh` or `glab`, as your project says. The Driver writes the PR description from
   the default template shipped in the skill
   (`skills/chantier/references/pr-template.md`), unless your project has its own template,
   which ranks above it.
6. **The Foreman reports back** (the Chief of Staff, in direct mode). You steer through the Chief
   of Staff (add, drop, a note on a CR; "I merged #42"); it forwards one `order` line to the
   Foreman. You merge; the Foreman merges only a release's PR or fix, on your word.
7. **A Release driver releases, when you ask.** It follows your project's own procedure, and
   stops for your approval before each irreversible action.

The agents do the work, git and the forge included. The `chantier` Python CLI (`uv run`) is
the frame beside them, in the planning folder (`.agents/changes/`, or an external surface), as plain JSON and Markdown: the CR lifecycle
(inbox, backlog, batch, archives, trash), the batch's limits (slots, budget, rounds, your word
on an irreversible action), the record (each CR's branch and worktree names, its PR, the long
gate's log, the cost, the `STATUS` files) and the lines that synchronise the team (orders, asks,
hand-backs, notes). It refuses what the batch does not allow and tells an agent what is off (an
unpushed head, a worktree not yet created); it decides nothing: the Foreman and the Drivers do,
under your project's own rules (`AGENTS.md` and what it links rank above chantier's cards).

chantier is four things in one repository:

1. **Four skills.** [`skills/chantier/`](skills/chantier/) holds the router (`SKILL.md` asks
   which role the session takes), the cards, the CLI and the assets; the entries
   [`skills/chief-of-staff/`](skills/chief-of-staff/), [`skills/griller/`](skills/griller/) and
   [`skills/status/`](skills/status/) are thin and load the same cards. [`references/`](skills/chantier/references/) holds one file per
   running context: `concepts.md` (read by everyone), `session-start.md` (the start checks, the
   seat, the session titles), `chief-of-staff.md`, `griller.md`, `status-layout.md`, `foreman.md`, `driver.md`, `worker.md`
   and `routing.md`; `pr-template.md` is the default PR description a CR Driver writes and the
   Inspector audits; `release-template.md` is the default release notes and announcement thread the
   release Driver writes when the project has none of its own; `hosts/claude-code.md` and
   `hosts/copilot.md` hold what is proper to a host (tools, heartbeat, sessions), each behaviour
   marked proved, documented or unproved, and the cards only point to them. They are written for agents: short, exact, one meaning per word. A card
   says what a role judges and how; the project's own rules (`chantier rules`) rank above it.
2. **A CLI** ([`skills/chantier/scripts/cli/`](skills/chantier/scripts/cli/)): a Python package
   declared in the root `pyproject.toml` and locked in `uv.lock`, on Linux, macOS and Windows. Installed
   as a plugin, it runs by `uvx --from "<plugin root>" chantier --skill "<skill folder>"`, from the
   plugin's own folder; in this checkout (a `.git` at the plugin root), by `uv run --locked --project
   "<root>" chantier`, the local code, live. Its scope is the frame
   the agents work in: the CR lifecycle (`file`, `triage`, `abandon`, `open`, the stages,
   `cancel`, `pause`, `close`), the batch's limits and record (`take`, `round`, `handback`,
   `ship`, `release go`; `rails.py` says what is refused), the means to synchronise (`order`,
   `asks`, `note`, `gate`, its lock and its stop) and a few tools (`rules`, `cost`). It runs no git
   command that changes anything (it reads the head, the remote and the status to say what is
   off) and no forge command: the agents have `git`, `gh` and `glab` and do the work. It writes
   only in the planning folder (the target repository's `.agents/changes/`, or the project's
   folder of an external planning surface, plus its own `.gitignore`), as plain JSON and
   Markdown: the CR folders in `1-inbox/`, `2-backlog/`,
   `3-ready/`, `4-batch/` (`1-pending/`, `2-actives/`, `3-done/`), `5-archives/` and `6-trash/`
   (each with a `work/` folder while it runs), and the batch's own files at the root of
   `4-batch/` (`batch.json`, `events.jsonl`, the brief, `STATUS.md`). The one write elsewhere is not the CLI's: on the user's yes, the Chief of Staff adds to `~/.claude/settings.json` the allow rules preflight's P10 named, and nothing else there. There is no configuration file: every agent reads the project's `AGENTS.md`.
   The CLI knows no role: the cards hold each role's contract, and the Foreman and the Drivers
   write the prompts. One named exception among the tools: `board`, a read-only web view of this
   record for the user in remote (it writes no file, is part of the CLI's package and runs with no plugin
   too (`uvx --from git+https://github.com/gsemet/chantier@v<version> chantier board`), and knows no role; more is another CR). A new CLI tool comes only from measured token-costly behaviour of the
   agents, never from speculation about what they might need.
3. **A plugin**: [`.github/plugin/`](.github/plugin/) (GitHub Copilot: `plugin.json` and the marketplace) and
   [`.claude-plugin/`](.claude-plugin/) (Claude Code) ship the skill
   and one agent per role and host: [`agents/`](agents/) for Claude Code (`chantier:<role>`),
   [`com.github.copilot/agents/`](com.github.copilot/agents/) for Copilot (`chantier-<role>`, a
   prefix a project agent named after the role cannot shadow). An agent file holds only its
   host's frontmatter (model, tools) and a short body; both hosts' bodies are identical, which the
   tests check. The Foreman is a session, not an agent: its model is in
   [`chief-of-staff.md`](skills/chantier/references/chief-of-staff.md), where it is started.

4. **A mod** ([`hooks/`](hooks/), Claude Code only): the CR board, a read-only pane over
   `.agents/changes/STATUS.json`. `hooks/hooks.json` names `register.tsx`, which
   hooks `skill.prompt`, `session.compact` (the automatic reload), the `/chantier-board` command
   and the `cr-board` pane, and guards the writes of a worker and a CR Driver (`agent.spawn` and
   `tool.call`: it starts an agent whose prompt holds a `writes:` line in its first folder and
   refuses its Write, Edit or NotebookEdit outside the folders named, and the Bash or PowerShell
   writes it can see; what it cannot see, such as an interpreter's inline code, is left to the
   cards); `types/index.d.ts`
   (named in `plugin.json`) is its contract. It writes nothing and runs no process but
   `git rev-parse`. Copilot has no such thing: its manifest names no hooks. The mod reads
   `STATUS.json` (`schema` 3) as `status.py` writes it: change both together. The CR board pane
   and `chantier board` show the same view (`schema` 3) and change with `status.py`.

The design rule that shapes everything: **no fallback.** When a tool, a host feature, a model
or an agent is not exactly available, chantier stops and says so; it never picks a look-alike.
Within what they have, the Foreman and the Drivers judge freely: the cards state
goals and boundaries, not procedures. Keep both true in any change.

### Repository layout

```text
.claude-plugin/             ← Claude Code plugin manifest and marketplace
.github/plugin/             ← GitHub Copilot plugin manifest and marketplace
agents/                     ← Claude Code agents, one per role
hooks/, types/              ← Claude Code only: the CR board mod and its contract, the reload after a compaction, and the guard of the writes of a worker and a CR Driver
com.github.copilot/agents/  ← Copilot agents, one per role (chantier-<role>)
skills/chief-of-staff/      ← the Chief of Staff's entry point (thin: it loads the cards below)
pyproject.toml, uv.lock       ← the CLI's package: the only declaration of its dependencies, and their lock
skills/griller/             ← the Griller's entry point (thin)
skills/status/              ← `/chantier:status`, the progress report (thin: it loads status-layout.md)
skills/chantier/
├── SKILL.md                ← the router: asks which role this session takes
├── references/             ← one file per running context: concepts, session-start,
│                             chief-of-staff, griller, report, foreman, driver, worker, routing,
│                             spec-writer, init,
│                             pr-template, release-template, and hosts/ (one
│                             reference per host: Claude Code, Copilot)
└── scripts/cli/            ← the `chantier` CLI's source, its tests and `session_usage.py`
scenario/                   ← one whole batch, scripted, no model
evals/                      ← eval campaigns with real agents, and their reports
scripts/                    ← version tooling, run by `just`
docs/                       ← diagrams, screenshots, the user docs (tutorial, use cases, reference pages), release notes
```

## Set up

Install [`uv`](https://docs.astral.sh/uv/), [`just`](https://just.systems/) and `git`.
Nothing else: `uv` fetches Python, the CLI's dependencies and the check tools (ruff, mypy).

To run your working copy in Claude Code, install the plugin from your checkout, once:

```bash
claude plugin marketplace add ./
```

```bash
claude plugin install chantier@chantier
```

The plugin is then read live from that checkout, and [`.claude/settings.json`](.claude/settings.json)
keeps it on in every session of this repository: a session here runs chantier itself, which is
how you debug it. An edit loads at the next session or with `/reload-plugins`, with no reinstall.
The main checkout is what runs: a branch switched there changes the plugin, and a worktree's work
counts once merged. After each merge it records, the steering session fast-forwards a clean main
checkout on `main`, so a merged fix to the CLI runs at once; the cards load at the next session or
with `/reload-plugins`.

In this checkout, `$CHANTIER` runs the local code, live, with no fetch (the dev mode: the plugin
root holds `.git`); an installed plugin runs its own folder with `uvx --from`.

## Daily work

```bash
just                # list the recipes
just check          # lint (ruff, mypy, the lock) and structure tests: run before any PR
just test -k agent  # structure tests, with pytest arguments
just scenario       # one whole batch, end to end, through the real CLI and a fake gh, then glab
just eval-dry-run   # the eval kit, end to end on a local sandbox: reset, setup, a staged run, audit, judge
just mod            # the mod: claude plugin validate, then claude plugin test (needs a claude binary)
```

The mod is checked apart from `just check` and CI, which have no `claude` binary. `just mod` is
the way to run `validate` and `test`: it finds `claude` on the `PATH`, else the executable of the
process `CLAUDE_PID` names (on Claude Desktop `claude` is not on the `PATH`), and stops with one
line when it finds none. It runs, from the repository's root:

```bash
claude plugin validate .        # the manifest, hooks.json and what register.tsx hooks and calls
claude plugin test .            # hooks/register.test.tsx, against the engine, no session
```

The type-check is by hand:

```bash
tsc -p <folder>                 # see below
```

`tsc` is not one of the project's tools: fetch it where you need it (`typescript` from npm).
Keep outside the mod folder a `<folder>/tsconfig.json`, with the options from the header of the
engine's `claude-code/index.d.ts`, and that d.ts under `<folder>/types/claude-code/`; its
`include` names those and the absolute paths of `hooks/` and `types/`.

`validate` warns about the marketplace description and the missing icon; those are known. The
tests stand in for the file system, the process and the session's folder with the engine's own
`on` hooks; they do not draw a real pane. A change to the pane therefore carries one screenshot
of it from a real session running the PR's head (the rule is in [AGENTS.md](AGENTS.md)). To run
the head: start a session with `claude --plugin-dir <worktree of the PR's branch>` (the flag is
in `claude --help` of the build seen, 2.1.321; other builds may differ). Unproved: that it
replaces the installed copy of the same name, that the board pane draws from it, that Claude
Desktop accepts it, and that `/reload-plugins` cannot point at a worktree (it reloads what is
already registered, the main checkout). Check the first two in the screenshot itself (a change
visible in the PR's head, absent on main).

- Repository text is in English.
- Write code and docs in the style of the surrounding files: short sentences, exact terms.
- Tests check the structure (versions, manifests, agents, references, and a smoke run in a fresh
  repository) in a few seconds. They do not evaluate the batch workflow: run `just scenario`
  ([scenario/](scenario/README.md)) when you change it; CI runs it too, on Linux. A change to the eval kit
  (`evals/kit/`) runs `just eval-dry-run`, as [Changing the kit](evals/README.md#changing-the-kit) says.
- A change that adds a CI job to `.github/workflows/`, or changes the steps of one, runs that
  job's steps once on the local machine before the push, in the workflow's order, with
  `UV_CACHE_DIR` set to a new empty folder (the same folder for every step of that run, outside
  the repository). A runner's uv cache is empty at each run and the local one is warm: a step that
  reads the cache passes every local gate and fails at its first CI run.
  - The steps repeated are the job's `run:` steps that do the job's work, a warm-up step included
    (such as the one before `just eval-dry-run`), which is so proved. The actions
    (`actions/checkout`, `astral-sh/setup-uv`, `extractions/setup-just`) and the steps that only
    set up the runner's machine are not repeated: above all the git identity step, whose
    `git config --global` must never touch the developer's own configuration.
  - The output is the Verifier's evidence (`work/verifier/evidence/`), quoted in the PR body.
  - A change that touches no CI job's steps does not owe it: a cold run downloads everything again.
  - The cold cache is the only local proof. Other differences with the runner (its system, the
    tools installed there) are proved by CI alone; the specification names them.
- With real agents, the [eval campaigns](evals/README.md): one quick campaign (`real-foreman`
  or `real-direct`, five frozen CRs on the sandbox) after a change to a role or the flow, in the
  mode it touched; `full` and both quick campaigns before a release (they read the main checkout: run them before
  the batch, or after the merge of everything under the version PR and before the user merges
  it); `claude-planted` after a
  change to how a batch handles
  failures; `copilot` for a change to Copilot's mechanics. Each run commits its report, with the
  [scorecard](evals/SCORECARD.md) for the Claude campaigns.
- `main` is protected: every change goes through a pull request, merged by rebase once CI
  (`just check` on Linux, macOS and Windows, and `just scenario` and `just eval-dry-run` on Linux) is green.

## Code standards

The plugin's Python (every `.py` file under `skills/`, tests included) meets these targets, and
`just check` enforces them on Linux, macOS and Windows through `just lint` and two tests
(`tests/test_code_targets.py`):

- **File:** at most 400 lines, one responsibility per module, no import cycle.
- **Function:** at most 50 lines, complexity at most 10, at most 5 arguments, 12 branches, 6
  returns, 50 statements, nesting at most 3 levels.
- **Style:** `ruff format` and `ruff check` clean (`E`, `W`, `F`, `I`, `B`, `UP`, `SIM`, `C90`,
  `PL`, `RUF`), lines of 100 at most; a `# noqa: <code>` names its code and says why.
- **Types:** every function annotated, `mypy --strict` clean.

The code of `src/chantier/` is in layers, and a module imports only from its own layer or the ones
below: `core/` (errors, files, clock, git, the JSON records as pydantic models, the repository,
the batch, the seat), then the domain modules (`lifecycle/`, `playbook/`, `costs/`, `status/`,
`rails.py`, `procs.py`, `plugin_files.py`), then `commands/` (one module per family of commands,
each with its `register(sub)`) and `board/`, then `cli.py`.

A dependency must replace hand-written code and ship wheels for Linux, macOS (x86_64 and arm64)
and Windows: the root `pyproject.toml` sets `no-build = true`, so nothing is built from source. After
a change to its dependencies, run `uv lock` (from the root); `just lint` refuses a stale lock. The board CRs add
the JS and CSS targets with their linter.

## Versions

One version, `MAJOR.MINOR.PATCH`, is carried by the CLI, the root `pyproject.toml` and `uv.lock`,
`SKILL.md`, the plugin manifests and marketplaces, and the agents. Never edit it by hand:

```bash
just version-show
just version 1.2.3            # an exact version
just bump-version             # patch; or `just bump-version minor`, `just bump-version major`
```

The script writes nothing if one file disagrees with the current version. Preflight refuses to
run when the skill, the CLI and the agents disagree, so every file must move together.

## Release

1. From an up-to-date `main` with green CI, or, for a release CR on top of a stack or a series,
   from the top CR's branch, take the version: the release CR's, else the Driver's choice, with
   its reason in the PR. Then, on a new branch, write the release folder `docs/release-notes/<today>-vX.Y.Z/` as
   [docs/release-process.md](docs/release-process.md) says.
2. Prepare the release. This bumps the version and runs `just check`, which refuses missing or
   invalid notes. It then stages `docs/release-notes/` and commits `release: vX.Y.Z`; it pushes
   nothing:

   ```bash
   just release          # patch; or `just release minor`, `just release major`
   ```

3. Push the branch and open the pull request. The user reviews the release folder in the PR's body
   and its files, and merges it by rebase once CI is green, last (in a stack, the stack in one action from
   the top PR or one PR at a time from the bottom, the release commit last; a change inserted into the stack makes the release PR update its
   release notes). That merge starts the next steps.
4. Tag the merged commit on `main` and push the tag:

   ```bash
   just tag
   ```

   It refuses unless origin/main's head is the `release: vX.Y.Z` commit of the local version, so
   a commit pushed after the merge never gets the tag.

5. Publish the reviewed notes as they are, with the images attached:

   ```bash
   uv run --script scripts/release_notes.py --prepare vX.Y.Z --output <tmp>/release-notes.md --assets <tmp>/assets
   gh release create vX.Y.Z --title vX.Y.Z --verify-tag --notes-file <tmp>/release-notes.md <each file that --prepare listed>
   ```

   `--verify-tag` makes `gh` refuse when the tag `just tag` pushed is not on the forge, instead
   of creating one.

   A typo found after publication is fixed by editing the release on GitHub. The published text
   may then differ from the file, and that is accepted.
6. The user posts the thread from `tweet.md`.

Users get the new version by updating the plugin from its marketplace, then restarting their
session.
