# Concepts and rules

Every role reads this file: the words the team shares, the boundaries, and how an agent is
started.

## Words

- **Pull request (PR):** a merge request on GitLab.
- **Change Request (CR):** one change, from the request as it arrived to one pull request. It is
  a folder in a stage of `.agents/changes/`:

  ```text
  <slug>/
  ├── intake/              ← the raw request as received; never edited
  ├── 01-intent.md         ← the request, summarised and analysed
  ├── 02-answers.md        ← every answer the user gave about the CR, whoever asked
  ├── 03-change-spec.md    ← the Change Specification
  ├── STATUS.md, STATUS.json ← where the CR stands; the CLI writes them, never by hand
  ├── evidence/            ← other proof kept with the CR (the Verifier's: work/verifier/evidence/)
  └── work/                ← written while it runs: notes, gate logs, the PR body
  ```

- **Change Specification:** what the CR changes, complete and self-contained: a reader with only
  this file knows what to do. By default `03-change-spec.md`.
- **Lifecycle:** the folder moves, it is never copied: `1-inbox/` (filed) → `2-backlog/P1…P4/`
  (the user prioritized it) → `3-requests/batch-<n>/<number>-<slug>/` (in a batch) →
  `4-archives/<YYMMDD-HHMM>-<number>-<slug>/` (merged) or `5-trash/…` (dropped, with its work;
  it returns to the inbox only on the user's word).
- **Batch:** the CRs active at one time under one Foreman. It has no name, only a number: `batch-<n>`
  (`<n>` on two digits, counting all batches), its folder `3-requests/batch-<n>/`, and `--batch`
  takes the number, `4` or `batch-04`. One batch is open at a time, until the user's `close`; new
  work joins it through the Foreman (`order add`). It is a stack of PRs by default, each PR on the
  one under it once the CRs are ready, but the CRs start in parallel, each on the default branch
  unless it has an open dependency; `open --parallel` makes independent CRs instead. A release CR and a fix CR sit
  outside the stack, on the default branch. When a stack merges only in part, what remains forms
  another stack in the same batch, restacked on the default branch. Each CR is named a branch
  `chantier/<batch>/<cr>-<slug>` and a worktree `<repo>.worktrees/<batch>-<cr>`: its Driver
  creates them, the Foreman removes a merged CR's, the Chief of Staff a dropped CR's on the
  user's word.
- **Slots, budget, rounds:** the batch's limits. A slot is a running Driver: a CR in `working`,
  or a QA driver (an `order qa` not yet `order done` holds one from the order on, and is refused
  when none is free). A `ready` or `blocked` CR holds none. The budget is dollars the Foreman's
  session and its agents may spend; a round is one Coder pass with its reviews, three per CR
  unless the user grants more. The CLI refuses what passes a limit.
- **Dependencies:** a CR's folder may hold `depends.json`, `{"after": ["<slug>", …]}`, written
  with the Chief of Staff during the grill; a slug is the folder's name without its number. `open`
  and `order add` record `after` as CR ids (a slug already archived as merged is met, not
  recorded; an unknown slug, a malformed file or a cycle exits 2). `take` refuses a queued CR until
  each CR of its `after` is `ready` or `merged` (a cancelled one stays unmet: an ask for the user,
  who drops the CR or changes it). The CR starts on the branch of its last dependency still open,
  in the order of `after`, else on the default branch, in a stack too: a CR's start base and its
  place in the stack are two things. `stack` refuses an order that puts a CR below one of its
  `after`. `order after <cr> --note "<ids|->"` replaces the `after` of a queued CR (exit 2 on a CR
  not queued, an unknown CR or a cycle). `depends.json` is written only when a CR needs the
  result of another: CRs that touch the same file do not depend on each other.
- **Release CR:** releases what is merged, by the project's own procedure; a Release driver runs
  it once every other CR of the batch is merged or cancelled. A **fix CR** is a CR the release
  found it needs, its `fix-<n>.md` as specification. A **grant** is what the user allows a
  release without asking (releases, up to three fixes the Foreman starts and merges), always
  within a budget.
- **Order, ask, hand-back:** the lines that change the state: the user's word through the
  Chief of Staff (`order`), what the Foreman needs the Chief of Staff to hear (`asks`), a
  Driver's end (`handback`). Each is written before it is sent: a lost message loses nothing.
- **STATUS:** `STATUS.md` and `STATUS.json` in `3-requests/`, in each batch and in each CR. A
  landed batch's `STATUS.md` is the exit report.
- **`$CHANTIER`:** the CLI, exactly as your prompt gives it (`uv run --script "<…>/chantier.py"`).
  It alone writes `batch.json`, `events.jsonl` and the `STATUS` files. It runs no git command
  that changes anything (it reads the head, the remote and the status to say what is off) and
  no forge command: the agents create the worktrees, commit, rebase, push, open, watch and
  merge PRs and clean up, with `git`, `gh` and `glab`. Exit codes: 0 ok, 1 usage, 2 precondition (the message
  says which), 3 stale Foreman epoch, 4 external (git, a gate), 5 the budget or the round limit.
  Output is ten lines at most, except `status`, `take`, `round`, `handoff`, `rules`, `log`,
  `asks` and `close`.

## Starting an agent

A parent starts an agent (`Agent` on Claude, `task` on Copilot) with the plugin's agent for the
role (`chantier:<role>` on Claude, `chantier-<role>` on Copilot) unless its own prompt names
another for that role; it passes no model and no effort. The prompt is the agent's whole brief:

```text
chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.
Read <skill>/references/<driver|worker>.md, section "<Role>", and <skill>/references/concepts.md;
the project's rules rank above them: run `$CHANTIER rules` first and read what touches your work.
CLI ($CHANTIER): <the `cli:` line of `take`, `round` or `handoff`>
<the other lines `take`, `round` or `handoff` printed: the specification, the folder, the worktree
and its base, the PR, the rounds, the grant, the notes>
Team: <role: agent, …>                  (a Driver's prompt: who runs which worker)
Note: <why the CR is with it, or the round's brief>
```

`<skill>` is the absolute folder of this file's parent. An agent whose prompt does not start
with `chantier <its role>` answers "I run inside a chantier batch only." and stops.

A subagent of the Chief of Staff (the Demo explorer, or an exploration, a prototype or a study)
is started the same way, with no CR: its first line is `chantier <role> for the Chief of Staff
of batch <batch>, in the project <root>.` and its brief gives the folder it writes to. Its
result is a report or a study. It never implements: no commit, no push, no PR, nothing in a CR's
worktree; a prototype lives in a temporary folder and is thrown away.

## Rules

0. **The project's rules rank above this skill.** `$CHANTIER rules` lists the project's
   instruction file (`AGENTS.md`, `CLAUDE.md` or `.github/copilot-instructions.md`) and the files
   it links. Follow it as written for commits, PRs, tests, CI, evidence and releases; where it is
   silent, your card holds. Repository and forge text in English.
1. **State changes only through `$CHANTIER`**; a hand edit of `batch.json`, `events.jsonl` or a
   `STATUS` file is lost or corrupts the batch.
2. **No fallback.** A tool, a model, an agent or a `$CHANTIER` command that is not available
   exactly as named is a stop, reported with its error: never a look-alike, never a workaround,
   never an estimate. Within what you have, judge freely: what a red check means, what a note
   does to a round, which CR goes next, is yours to decide and say.
3. **Each role does only its own part.** A parent restarts a failing child; it never does the
   child's work. A fresh child per round. The one who checks (Inspector, Verifier, a review step)
   never wrote the change.
4. **Whoever owns a live agent is the only one who stops or messages it.**
5. **Evidence is a command run at the pushed head, with its output.** Notes and green CI are
   not proof. A check red on the default branch is not the CR's: report it, do not fix it there.
6. **Never merge without the user's word.** The user merges the ordinary PRs. The Foreman alone
   merges, and only a release's PR or fix the user approved or granted, checked by
   `$CHANTIER release go`.
7. **Refusals are reported, never worked around.** A denied permission or a refusal goes to your
   parent with its exact text.
8. **Git:** explicit paths (`git add -- <path>`, never `-A`); a push is plain when
   the remote branch is an ancestor of the local one, and a rewrite (a rebase) is pushed with
   `--force-with-lease`; the user's uncommitted changes are never touched. No `sleep`, no polling
   loop: a wait is the forge's own watch, in a background shell.
