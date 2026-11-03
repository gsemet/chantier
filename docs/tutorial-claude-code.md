# Tutorial: chantier in Claude Code, step by step

This tutorial takes you from nothing to a merged pull request made by a chantier batch, in the
Claude Desktop app. It takes about twenty minutes, most of it waiting for the team to work.

You need:

- the **Claude Desktop app**, with its Code tab. chantier starts the Foreman as a nested session,
  which only the Desktop app can do: Claude Code in a terminal or in VS Code refuses to start a
  batch, on purpose;
- [`uv`](https://docs.astral.sh/uv/), `git`, and the [GitHub CLI](https://cli.github.com/) `gh`,
  logged in (`gh auth status`);
- a GitHub repository you can push to, cloned on your machine.

## 1. Install the plugin

In a terminal:

```bash
claude plugin marketplace add gsemet/chantier
```

```bash
claude plugin install chantier@chantier
```

This installs one skill (the Chief of Staff) and nine agents (`chantier:cr-driver`,
`chantier:coder`, …). Restart the Desktop app so it loads them. There is nothing else to install
and nothing to configure.

## 2. Tell chantier how your project builds

chantier reads your project's `AGENTS.md` (or `CLAUDE.md`) to learn how to check a change. If you
have neither, add an `AGENTS.md` at the root of the repository with at least:

```markdown
# AGENTS.md

- Default branch: `main`.
- Quick check before handing back: `npm run lint && npm test -- --changed`.
- Full suite: `npm test`.
- Commits follow Conventional Commits.
```

The quick check is the **fast gate** (run after every round of code), the full suite the **long
gate** (run once before the PR). One command may serve as both. On Windows, gates run in
`cmd.exe`.

## 3. Open the repository and meet the Chief of Staff

In the Desktop app, open the Code tab on your repository's folder (its root, not a worktree), and
type:

```text
/chantier:chantier prepare yourself to work on this project
```

The Chief of Staff introduces chantier in a few lines, reads your `AGENTS.md`, and records what
it learned: the gates, the default branch, where CR folders go. It shows you the result and asks
about anything your instructions do not settle. All of this lives in `.git/chantier/`: your
working tree is untouched.

You can check at any time:

```text
chantier, what do you know about this project?
```

## 4. File a change

```text
chantier, file this: the login form should show an error when the password is empty.
```

The Chief of Staff creates a **Change Request** folder in `.agents/changes/backlog/1-inbox/`, with
your request kept as written. Then it asks the questions that change the result ("only on submit,
or as you type?"), each with its recommended answer, records your answers in `02-answers.md`, and
writes the **Change Specification** (`03-change-spec.md`). Read it: it is exactly what the team
will build.

File as many items as you like. To prioritize one:

```text
make it a P1
```

## 5. Run a batch

```text
run the P1s, two at a time
```

The Chief of Staff:

1. runs the **preflight** (Desktop app, plugin agents, `uv`, main checkout, project instructions)
   and stops with the reason if anything is missing;
2. shows you the plan: the CRs, the slots, the gates, the agents;
3. waits for your **go**.

Say "go". It opens the batch (each CR gets a branch `chantier/<batch>/…` and a worktree next to
your repository), then starts the **Foreman** in its own session and detaches it. You will see
that session in the sidebar; you never need to talk to it.

## 6. Follow and steer

While the team works, keep talking to the Chief of Staff:

| You say | What happens |
| --- | --- |
| "status?" | one line per CR, with its PR link and CI state |
| "drop CR-102" | the Foreman stops its Driver; the folder goes back to the backlog |
| "CR-103 first" | it gets the next free slot |
| "for CR-101, also handle the remember-me checkbox" | the Driver takes it into its next round |
| "what did it cost?" | the measured cost so far, by role or by CR |

When a CR needs a decision only you can take, the Chief of Staff brings you the question. Your
answer is recorded in the CR's `02-answers.md` and the work resumes.

## 7. Review and merge

When a CR is ready, the Chief of Staff gives you its pull request. Each PR was built in rounds
(Coder, then a fresh Inspector), passed the long gate and CI, and was checked at its pushed head
by a Verifier that did not write it. Review it like any PR. **chantier never merges**: you do.

After merging, tell it:

```text
I merged #42
```

The CR's folder moves to `4-archives/`. When every CR of the batch is merged or dropped, the
Foreman lands the batch: it removes the merged worktrees, writes a report, and ends.

## 8. Make the team yours

Any role can run one of your own agents (in `.claude/agents/` or `~/.claude/agents/`), and you
can add review steps:

```text
use my rust-coder agent as the coder
add a security review with my sec-reviewer agent: OWASP top 10 on the diff
which agents and models?
```

A built-in role keeps its contract (the spawn prompt carries it), so your agent only brings its
model, tools and know-how. A new role runs after the Inspector approves each round and answers with
the same verdict. The next batch uses the new team; a running batch keeps its own.

By default the Foreman runs on Opus 5.5 and every other agent on Sonnet 5.5; run your own session
(the Chief of Staff) on Opus 5.5.

## If something goes wrong

- **"chantier cannot run here: nothing was started."** The preflight names the failed condition
  and what to do. The usual one: you are in the terminal or VS Code; open the Desktop app.
- **The app restarted during a batch.** Say "resume". The Chief of Staff checks the Foreman, and
  on your word starts a new one that picks up every CR where it was.
- **A CR is blocked.** "status?" shows why; answer the question or drop the CR.
- Anything refused (a permission, a tool, a model) is reported with its exact text: chantier
  never works around a refusal.

Next: [use cases](use-cases.md) for more ways to work with chantier.
