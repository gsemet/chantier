# Concepts and rules

Every role reads this file. It holds the words the team shares and the rules a capable model
would not follow on its own here, each with its reason.

## Words

- **Pull request (PR):** a merge request on GitLab; the CLI talks to either forge.
- **Change Request (CR):** one change, from the request as it arrived to one pull request. It is
  a folder under `.agents/changes/backlog/`:

  ```text
  <slug>/
  ├── intake/              ← the raw request as received (prompt text, exported issue); never edited
  ├── 01-intent.md         ← the request, summarised and analysed; names its intake files
  ├── 02-answers.md        ← every answer the user gave about the CR, whoever asked
  ├── 03-change-spec.md    ← the Change Specification
  ├── evidence/            ← proof a QA driver or Verifier keeps with the CR
  ├── work/                ← written while it runs: notes, gate logs, the PR body
  └── research/…           ← anything else useful
  ```

- **Change Specification:** what the CR changes, complete and self-contained: a reader with only
  this file knows what to do. By default `03-change-spec.md`.
- **Lifecycle:** the folder moves, it is never copied: `1-inbox/` (filed, unprioritized) →
  `2-backlog/P1…P4/` (the user prioritized it) → `3-requests/` (in a batch, renamed
  `<number>-<slug>`) → `4-archives/` (merged) or back where it came from (dropped);
  `5-trash/` only on the user's explicit word.
- **Batch:** the CRs the user starts together, in parallel or as a stack of PRs. Each CR gets a
  branch `chantier/<batch>/<cr>-<slug>` and a worktree next to the repository.
- **Release CR:** a CR that releases what is merged, by the project's own procedure, with or
  without a commit. A Release driver runs it, once every other CR of the batch is merged or
  cancelled. A **fix CR** is a CR the release found it needs; the release starts again after it.
- **Grant:** what the user allowed a release to do without asking: a number of releases, the
  merge of its fixes, always within a budget. Without one, each irreversible action waits for
  the user.
- **Work folder:** the CR's `work/`; your spawn prompt gives its path.
- **`.agents/changes/`:** the one folder chantier writes in, as plain JSON and Markdown:
  `backlog/` (the CR folders) and `batches/<batch>/` (`batch.json`, `events.jsonl`, `brief.md`,
  `report.md`). The project's `AGENTS.md` is the only configuration: the Chief of Staff reads it
  and passes the gates, the branch and the team to `$CHANTIER open`.
- **`$CHANTIER`:** the CLI, exactly as your prompt gives it (`uv run --script "<…>/chantier.py"`).
  It alone writes `batch.json` and `events.jsonl`.

## Rules

1. **State changes only through `$CHANTIER`.** Several agents write the batch at once; the CLI
   locks, writes atomically and logs the event. A hand edit is lost or corrupts the batch.
2. **Fail, never improvise.** When a precondition fails, a tool, command, host feature or agent
   is missing or refused, stop: start nothing, return `blocked` with the error as printed. Never
   substitute another tool, model, agent, mechanism or estimate, even one that looks close. A
   workaround costs tokens, hides the defect and makes the next run unpredictable; a clear stop
   costs one question to the user.
3. **Each role does only its own part.** A parent restarts a failing child and never does the
   child's work: a parent that codes or reviews fills its context with work it cannot hand over.
4. **Whoever owns a live agent is the only one who stops or messages it.** A session cannot reach
   another session's background agents; a message to a busy agent waits for its next turn.
5. **A fresh child per round.** A resumed agent keeps a stale picture; the specification and the
   round notes in the work folder carry what the next one needs.
6. **The one who checks never wrote it.** The Inspector, the Verifier and every extra review step
   are new agents: their value is that they share none of the Coder's assumptions.
7. **Evidence is a command run at the pushed head**, with its output. Notes, summaries and green
   CI are not proof.
8. **Two failed fixes on one premise: test the premise.** A third fix on it usually fails the same way.
9. **A check red on the default branch is not the CR's.** Fixing it inside the CR hides the fix
   in the wrong PR; report it.
10. **Never merge.** The user merges; a batch lands only when every CR is merged or cancelled.
    The only exception is `$CHANTIER merge`, which refuses all but what the user allowed: a
    release's fix under the grant, the release's own PR after `release go`.
11. **Refusals are reported, never worked around.** A denied permission, a classifier or app
    refusal goes to your parent with its exact text; never retried in another form or handed to
    another agent.
12. **Project conventions win.** Follow the project's `AGENTS.md` (or `CLAUDE.md`) and the
    guidance it links for commits, PRs, tests and evidence. Repository and forge text in English.

## Everyday mechanics

- **Git:** stage explicit paths only; the only rewrite is a rebase pushed with
  `--force-with-lease` (`$CHANTIER ship` does it); never touch the user's uncommitted changes.
- **Environments:** never delete `.venv`, `node_modules` or caches; install dependencies only if
  the project or the CR allows it.
- **Shell:** commands never wait for input (`GH_PAGER=cat GH_PROMPT_DISABLED=1 GIT_EDITOR=true`);
  no `sleep`, no polling loop: waits go through `$CHANTIER wait` in the background.
- **Output:** a `$CHANTIER` command prints at most ten lines (`--json` gives everything). Exit
  codes: 0 ok, 1 usage, 2 precondition (the message says which), 3 stale Foreman epoch,
  4 external tool (git, gh or glab, a gate), 5 budget. Exit 2 on a lock held over 30 s: retry once,
  then report it.
