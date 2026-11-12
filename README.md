# Chantier

The construction site for your Software Factory.

- **Change Requests beside your tracker.** A Change Request (CR) is one more level over your
  tracker's issues: small requests are accepted and prioritised here, without entering the
  tracker ([more](#change-requests-lifecycle)). A CR is a folder whose content varies, from one
  line of text to several HTML prototypes; the agents read it and find the request's intent.

  CRs are fungible in the plan: they can be handled, split, and so on.
- **Working in batches.** chantier is not continuous delivery (1 intent = 1 PR = 1 release). It is
  n CRs → m PRs (normally close to n) → p batches (1, 2, 3...) → 1 release.
- **One person to talk to.** You talk to the Chief of Staff, in your own session. It keeps the
  backlog and asks the questions a change needs. Nothing starts without your go, and you merge
  the pull requests. Optional: a Griller session grills beside it.
- **Direct or Foreman.** The Chief of Staff steers a batch itself (direct mode), or a nested
  Foreman session steers it (Foreman mode). In both a CR added while the batch runs is queued
  and taken when a slot frees. Direct mode is simpler to use remotely, from a phone; Foreman mode
  lets you grill future topics with the Chief of Staff naturally while the Foreman runs the batch.
- **Respect the project's rules.** Your changes must be able to land without chantier: chantier is
  there to industrialise. Your `AGENTS.md`, and an optional `chantier.yaml` at the project's root
  (the agent and model of each role, the skills it needs), are the only configuration. Everything
  chantier writes is Markdown and JSON in the planning folder: `.agents/changes/` in your project,
  or the project's folder of an [external planning surface](docs/planning-modes.md).

## How Chantier works

The detailed view first, then two simpler views, one per mode.

![How chantier works](docs/how-chantier-works.svg)

**Foreman mode** (`/chantier:chief-of-staff`): a nested Foreman session steers each batch, at the
desktop; your Chief of Staff stays free for a natural, dynamic conversation while it runs.

![How chantier works, in Foreman mode](docs/how-chantier-works-simple-foreman.svg)

**Direct mode** (`/chantier:chief-of-staff direct`): the Chief of Staff steers the batch itself;
it works in a remote session; to grill while a batch runs, open a Griller session.

![How chantier works, in direct mode](docs/how-chantier-works-simple-direct.svg)

The difference that matters most: in direct mode the Chief of Staff, busy steering, holds no
grill while the batch runs; in Foreman mode it stays free to grill. In both, a new CR can join
the running batch and waits for a free slot.

## Planning modes

Chantier plans in one of two places, the **planning folder**:

- **In-project** (the default, nothing to declare): `.agents/changes/` in your project.
- **External**: a git repository of its own, the *planning surface*, with one folder per project
  (`projects/<name>/` with `project.md`, `checkout.yml` and `changes/`). Your project's repository
  gets only the code and, if you want, each CR's cleaned archive in its PR.

The Chief of Staff, the Foreman and the Griller run on the default branch: your project's main
checkout in-project, the surface's checkout in external mode. Only the code gets worktrees: each
CR's Driver and workers, in your project; a Griller in a never-merged worktree, in remote. About
remote sessions, this is the author's own finding, not a proved trial: a remote session cannot start
outside a worktree, so the Chief of Staff starts locally, then goes remote (Remote Control).

![Planning modes: in-project and external](docs/planning-modes.svg)

The full account (the surface, what stays local, archives, outside contributors, privacy, setting
one up) is in [planning modes](docs/planning-modes.md).

## Batch modes

A batch has one of three modes. They say how the pull requests of the batch relate, and who merges
what, when. You never merge through chantier: you merge, and the steering session guides you.

![Batch modes: parallel, series and stack](docs/batch-modes.svg)

- **Parallel** (the default; ask for nothing): every CR starts from the default branch at once and
  its PR is on the default branch. The first one ready wins: you merge in the order things become
  ready, unless you say otherwise. After each merge, every PR still open is rebased onto the
  default branch and its checks run again, conflict or not.
- **Series** ("run these in series"): the CRs have a precise order, the one you gave. The next CR
  starts once the previous one is handed back ready, from the previous CR's pushed branch, and its
  PR is a draft. Once the previous one merges, the next one is rebased onto the default branch and
  turns ready. The Chief of Staff guides you merge by merge. On request ("switch to a stack"), a
  series becomes a stack at once.
- **Stack** ("build a stack of these"): parallel, with a stack driver. Every CR starts at once, the
  PRs go each on the previous one, and the stack driver keeps the stack up to date; you merge from
  the bottom up.

A CR that depends on another (`depends.json`) waits for it in every mode. A release CR and a fix CR
sit outside a series and a stack. The lifecycle of a batch (running, paused, closed) is the same in
all three.

## Change Requests Lifecycle

A "Change Request" is one more level over the issues of your tracker (Jira, GitHub, GitLab...).
Small requests that do not belong in the tracker (an idea, a bug, a report) are accepted and
prioritised as CRs. The tracker keeps the strategic vision, the external requests and the long-term planning.
The planning folder, in your project or external, is the tactical, short-term plan, the closest to
the work site; Jira, GitLab work items or GitHub issues keep the strategic, long-term plan, or
serve as the interface for outside customers and support.

Chantier turns each request into a folder in the planning folder, carried through planning, study, implementation, QA, deployment and finally archive.

![docs/cr-lifecycle-simple.svg](docs/cr-lifecycle-simple.svg)

Several files, essentially markdown will be injected into the folder with prototypes, studies, spec, reports,...

Some names are mandatory, you are free to add any you see fit (svg, drawio, ...).

Custom connection to any external tools is also possible, as long as it translates to a text, XML, SVG, or local file an agent can interpret with our without specialized tools.

![docs/cr-folder-lifecycle.svg](docs/cr-folder-lifecycle.svg)

## Detailed lifecycle

This displays the major operations:

- Planning, mainly with the Chief of Staff
- the central implementation loop, which delegation to drivers and strict reviews
- a QA loop, where a validation agent can act like a user to validate all that is **not** validated by the integration, e2e tests
- release process with supervised auto-merge, that can monitor the deployment (to production environment, to package registries, to documentation pages,...)

![cr-lifecycle](docs/cr-lifecycle.svg)

## Releases

A release is a CR like the others: a Release driver runs it by your project's own release procedure, from your "release" to the archive. You approve each irreversible action, or say "auto".

![What a Release driver does](docs/release-driver.svg)

## What is Chantier?

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
3. **You start a batch** ("run the P1s"; four slots; the CRs run in parallel unless you ask for a [series or a stack](#batch-modes)). After a preflight and your go, the
   Chief of Staff starts one **Foreman** in a nested session. In **direct mode** (proposed when the
   host cannot start a Foreman session, or the batch is small) no Foreman starts: the Chief of
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

## Install

chantier is a [Claude Code plugin](https://code.claude.com/docs/en/plugins), a GitHub Copilot
plugin and an [Agent Plugin](https://agent-plugins.org/): one skill and one agent per role and
host. Claude Code and Copilot get different agents: their tools and model fields differ.

On Claude Code:

```bash
claude plugin marketplace add gsemet/chantier
```

```bash
claude plugin install chantier@chantier
```

On GitHub Copilot:

```bash
copilot plugin marketplace add https://github.com/gsemet/chantier.git
```

```bash
copilot plugin install chantier@chantier
```

New to chantier? Follow the [step-by-step tutorial for Claude Code](docs/tutorial-claude-code.md),
then browse the [use cases](docs/use-cases.md), with one page per configuration:
[Foreman mode](docs/use-cases-foreman.md) and [direct mode](docs/use-cases-direct.md). To plan
outside your project's repository, see [planning modes](docs/planning-modes.md).

Then restart the session and type one of the entries (on Claude Code, `/chantier:<name>`):
`/chantier` asks which role this session takes, `/chief-of-staff` makes it the Chief of Staff
(`/chief-of-staff direct` to steer batches itself), `/griller` makes it a Griller, a session that
refines the inbox and the backlog while the Chief of Staff runs batches, and `/chantier:status` gives the progress report of the running batch at once, in the same shape as the Chief of Staff's. Besides
the plugin, the only thing to install is [`uv`](https://docs.astral.sh/uv/); working on a
repository also needs `git` and the forge's CLI, logged in: `gh` for GitHub, `glab` for GitLab.

## Use

Talk to the Chief of Staff in plain language:

| You say | What happens |
| --- | --- |
| "init", "I am new here" | the five stage folders are created, then a guided tour of how your project works with chantier |
| "become chief of staff" (`/chief-of-staff`) | this session takes the seat: the one session that opens and runs batches in the repository |
| "you are a griller" (`/griller`) | this session refines the inbox and the backlog, never opens a batch; the Chief of Staff picks up what it files |
| "status?" (`/chantier:status`) | the progress report: the table of CRs, their state, their PR and the cost; it changes nothing |
| "chantier reload" (`/chantier:chantier reload`) | the session reads chantier's rules again, typically after a compaction; on Claude Code the plugin also does it by itself at every compaction |
| "file this idea" | a CR folder in the inbox; it can be refined at any stage |
| "make it a P2" | it moves into the prioritized backlog |
| "it is grilled enough" | the spec-writer writes the Change Specification in the background |
| "run the P1s", "run these in series", "build a stack of these" | preflight, questions, the plan, then a Foreman starts on your go, or the Chief of Staff steers in direct mode |
| "status?" | one line per CR with its PR; a blocked CR comes back as a question |
| "drop CR-103", "I merged #42" | an order for the steering session (the Foreman, or the Chief of Staff in direct mode), never a direct action on a Driver |
| "close the batch" | the check and the final cost, then closing on your yes |
| "release v1.4.0" | a release CR, run by your project's procedure; you approve each irreversible action |
| "what did it cost?" | measured cost: the Foreman, each Driver type, each worker type, and why |
| "use my `rust-coder` agent as the coder" | that role runs your agent from the next batch |
| "add a security review with `sec-reviewer`" | a new review step the Driver runs after the Inspector |
| "our long gate is `npm test`" | the Chief of Staff proposes the exact `AGENTS.md` lines and writes them on your yes (see [Your gates](docs/gates.md)) |
| "which agents and models?" | the team: each role, its agent, its model (`chantier playbook`) |
| "run the inspector on Opus" | a `model` for the role in `chantier.yaml`, which the CLI resolves to the exact model (or refuses an unknown or ambiguous name) |

## More

- [Boards](docs/boards.md): the CR board and the remote board.
- [Your gates](docs/gates.md): the fast gate and the long gate you declare in your `AGENTS.md`.
- [Your own agents and models](docs/agents-and-models.md): which agent and model each role runs.
- [The planning folder](docs/planning-folder.md): its layout, and a batch's pause and close.
- [Supported hosts](docs/hosts.md): hosts, forges and Windows.
- [Costs and budgets](docs/costs.md): what a batch costs and how it is capped.

## Repository layout

```text
.claude-plugin/             ← Claude Code plugin manifest and marketplace
.github/plugin/             ← GitHub Copilot plugin manifest and marketplace
agents/                     ← Claude Code agents, one per role
hooks/, types/              ← Claude Code only: the CR board mod and its contract, the reload after a compaction, and the guard of a worker's writes
com.github.copilot/agents/  ← Copilot agents, one per role (chantier-<role>)
skills/chief-of-staff/      ← the Chief of Staff's entry point (thin: it loads the cards below)
skills/griller/             ← the Griller's entry point (thin)
skills/status/              ← `/chantier:status`, the progress report (thin: it loads status-layout.md)
skills/chantier/
├── SKILL.md                ← the router: asks which role this session takes
├── references/             ← one file per running context: concepts, session-start,
│                             chief-of-staff, griller, report, foreman, driver, worker, routing,
│                             spec-writer, init,
│                             pr-template, release-template, and hosts/ (one
│                             reference per host: Claude Code, Copilot)
└── scripts/cli/            ← the `chantier` CLI and its tests
scenario/                   ← one whole batch, scripted, no model
evals/                      ← eval campaigns with real agents, and their reports
scripts/                    ← version tooling, run by `just`
docs/                       ← diagrams, the user docs (tutorial, use cases, reference pages), release notes
```

## Develop

See [CONTRIBUTING.md](CONTRIBUTING.md) for how the project is built and how a release is made.

```bash
just check                  # structure tests (a few seconds)
just scenario               # one whole batch, end to end, no model
```

See [`evals/README.md`](evals/README.md) for the eval campaigns with real agents (full,
real-foreman, real-direct, claude-planted, copilot), how to run one, and their last results.
