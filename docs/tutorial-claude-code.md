# Tutorial: chantier in Claude Code, step by step

This tutorial takes you from nothing to a merged pull request made by a chantier batch, in the
Claude Desktop app. It takes about twenty minutes, most of it waiting for the team to work.

You need:

- the **Claude Desktop app**, with its Code tab. chantier starts the Foreman as a nested session,
  which only the Desktop app can do: Claude Code in a terminal or in VS Code refuses to start a
  batch, on purpose;
- [`uv`](https://docs.astral.sh/uv/), `git`, and your forge's CLI logged in to its host: the
  [GitHub CLI](https://cli.github.com/) `gh` (`gh auth status`) or the
  [GitLab CLI](https://gitlab.com/gitlab-org/cli) `glab` (`glab auth status`), self-hosted
  servers included;
- a GitHub or GitLab repository you can push to, cloned on your machine.

We recommend turning on "Connect new sessions to Remote Control" in the app's settings: you can
then follow the Foreman's session from your phone, and answer it there when it needs your word.

## 1. Install the plugin

In a terminal:

```bash
claude plugin marketplace add gsemet/chantier
```

```bash
claude plugin install chantier@chantier
```

This installs one skill (the Chief of Staff) and ten agents (`chantier:cr-driver`,
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

The quick check is the **fast gate** (the Coder runs it after every round), the full suite the
**long gate** (the Driver runs it once before the PR, through `chantier gate`, alone in the
repository). One command may serve as both. On Windows, the long gate runs in `cmd.exe`.
Everything else `AGENTS.md` says (how to commit, the PR template, the merge method, what a
skipped job means, how to release) binds the team too: the Drivers commit, push and open the
PRs themselves, and your rules rank above chantier's own.

## 3. Open the repository and meet the Chief of Staff

In the Desktop app, open the Code tab on your repository's folder (its root, not a worktree), and
type:

```text
/chantier:chantier prepare yourself to work on this project
```

The Chief of Staff introduces chantier in a few lines, reads your `AGENTS.md`, and tells you
what it learned: how you check, ship and merge, and the default branch. It asks about anything your instructions do
not settle, and offers to write the answer in `AGENTS.md`. It records nothing anywhere else: it
reads `AGENTS.md` again at every session, and everything chantier writes later goes to
`.agents/changes/`.

You can check at any time:

```text
chantier, what do you know about this project?
```

## 4. File a change

```text
chantier, file this: the login form should show an error when the password is empty.
```

The Chief of Staff creates a **Change Request** folder in `.agents/changes/1-inbox/`, with
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

1. runs the **preflight** (Desktop app, plugin agents, `uv`, main checkout, project
   instructions, the forge's CLI logged in) and stops with the reason if anything is missing;
2. shows you the plan: the CRs, the slots, the budget, the agents;
3. waits for your **go**.

Say "go". It opens the batch (each CR is named a branch `chantier/batch-<n>/…` and a worktree
next to your repository, which its Driver creates when it starts), then starts the **Foreman**
in its own session. You will see that session in the sidebar; you never need to talk to it.

## 6. Follow and steer

While the team works, keep talking to the Chief of Staff:

| You say | What happens |
| --- | --- |
| "status?" | one line per CR, with its PR link |
| "drop CR-102" | the Foreman stops its Driver; the folder goes to `5-trash/` |
| "CR-103 first" | a note on the CR; the Foreman gives it the next free slot |
| "for CR-101, also handle the remember-me checkbox" | a note on the CR; the Driver takes it into its next round |
| "what did it cost?" | the measured cost so far: the Foreman, each Driver type, each worker type |

When a CR needs a decision only you can take, the Chief of Staff brings you the question. Your
answer is recorded in the CR's `02-answers.md` and the work resumes.

## 7. Review and merge

When a CR is ready, the Chief of Staff gives you its pull request. Each PR was built in rounds
(Coder, then a fresh Inspector), passed the long gate and CI, and was checked at its pushed head
by a Verifier that did not write it; the Driver committed, rebased, pushed and opened it by your
project's rules. Review it like any PR. **chantier never merges your PRs**: you do (only a
release's PR or fix is merged by the Foreman, on your word).

After merging, tell it:

```text
I merged #42
```

The CR's folder moves at once to `4-archives/`, named by the time of the merge. When every CR of
the batch is merged or dropped, the Foreman removes the merged CRs' worktrees and branches with
git, lands the batch (its `STATUS.md` is the exit report, its cost not final) and goes idle.
Then the Chief of Staff runs `chantier close` without `--yes`, which refuses while anything
still runs or the final cost cannot be priced (it names the cause) and otherwise prices it; it shows what closing deletes (the batch folder,
the dropped CRs' worktrees and branches) and that cost; on your yes, `chantier close --yes` deletes the folder and it removes the rest with git.
Without a yes, everything stays.

## 8. Make the team yours

Any role can run one of your own agents (in `.claude/agents/` or `~/.claude/agents/`), and you
can add review steps:

```text
use my rust-coder agent as the coder
add a security review with my sec-reviewer agent: OWASP top 10 on the diff
which agents and models?
```

The Chief of Staff writes them in a `chantier` section of your `AGENTS.md`:

```markdown
## chantier

- coder: `rust-coder`
- security-review: `sec-reviewer`, after the Inspector: OWASP top 10 on the diff
```

A built-in role keeps its contract (its card in the skill, named in the prompt the Driver
writes), so your agent only brings its model, tools and know-how. A new role runs after the Inspector approves each round and answers with
the same verdict. The next batch uses the new team; a running batch keeps its own.

By default the Foreman and the CR, stack and release drivers run on Opus 5.5 (they judge: what
goes next, what a red check means), the QA driver and the workers on Sonnet 5.5; run your own
session (the Chief of Staff) on Opus 5.5 too.

None of them needs a 1M-token context. The plugin's agents compact at 200,000 tokens
(`autoCompactWindow` in their files). The Foreman is a session of its own, which chantier cannot
configure: to keep it lean too, set the window in your user settings, `~/.claude/settings.json`
(400,000 leaves the Foreman room for a long batch). It applies to every session you run, yours
included.

```json
{ "autoCompactWindow": 400000 }
```

## If something goes wrong

- **"chantier cannot run here: nothing was started."** The preflight names the failed condition
  and what to do. The usual one: you are in the terminal or VS Code; open the Desktop app.
- **The app restarted during a batch.** Say "resume". The Chief of Staff checks the Foreman, and
  on your word starts a new one that picks up every CR where it was.
- **A CR is blocked.** "status?" shows why; answer the question or drop the CR.
- Anything refused (a permission, a tool, a model) is reported with its exact text: chantier
  never works around a refusal.
- **The Foreman was refused an action by a classifier.** It wants your word in that session: type
  one line in the Foreman's session allowing that action, from your phone if you are away.

Next: [use cases](use-cases.md) for more ways to work with chantier.
