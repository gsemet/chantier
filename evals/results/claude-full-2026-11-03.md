# claude-full, 2026-11-03

**Verdict:** passed with findings. All five changes were built, reviewed and merged by the agents
without help, but the run showed waste and gaps; every finding below has been fixed since, in
[gsemet/chantier#8](https://github.com/gsemet/chantier/pull/8).

This run used an earlier version of the campaign: five CRs, no failure path (no red CI, no round
limit).

## What was tested

chantier was asked to make five small changes to `tasks-cli`, a to-do list program, each as its
own pull request. Three started together; two more were added while the team worked. During the
run, the user changed one request, answered one question, and merged each pull request when it
was ready.

## What happened

- **CR-101, add a priority to tasks.** Built and approved in one round, merged first.
- **CR-102, a crash on an unknown task number.** The project's documentation reviewer asked for
  the README to explain the new error; fixed in a second round. The user then asked for the
  error to go to the error stream; the team did it. Merging the other changes first put it in
  conflict; a conflict resolver fixed that, and it was merged.
- **CR-103, a JSON output for the list.** Built in one round. A QA agent used the program as a
  user would (empty list, a few tasks, JSON validity) and found nothing. Merged second.
- **CR-104, a delete command.** Added during the run, built in one round, merged last. Each time
  another change was merged, it had to be redone on top: three Drivers in a row, and each started
  over from scratch instead of picking up the work already done.
- **CR-105, a CSV export.** Added during the run. Its request left the columns to the user: the
  Driver stopped and asked before writing any code. Once answered, a new Driver built it, and it
  was merged.

## Findings

1. **When `main` moved, nobody brought the ready pull requests up to date.** The user had to order
   each rebase by hand. Now, after each merge, the ready ones that no longer merge cleanly go
   back to a Driver on their own.
2. **A restarted Driver redid the whole change.** CR-104 was coded three times. Now a new Driver
   picks up where the last one stopped.
3. **The round counter counted each review as a round** (CR-102 showed 6 for about 3). Now the
   CLI numbers rounds itself, once per round.
4. **The rule for a Driver's question differed by host**, and the Driver mixed the two. Now there
   is one rule: a question ends the Driver's run, and the answer goes to a new Driver.
5. **One Driver started a reviewer with a prompt of its own** (1 agent in 59). Now the prompt gives
   the exact command, and a wrong one says which to use.
6. **The cost per change left 28% under "other".** Now every agent counts for its change.
7. **The Foreman cost 46% of the run** on Opus, for a job the CLI decides. It now runs on Sonnet.
8. **The QA kept no proof** of what it tried. It must now, or it cannot finish.
9. **A batch report could say "Spent: $0.00"** (seen in the one-CR rehearsal). The report now
   measures the cost itself.

## Numbers

- **Duration:** 2 hours (14:06 to 16:07 UTC).
- **Cost:** $8.51 in all.
  - By role: Foreman $3.91, Drivers $1.74, verifiers $0.74, coders $0.72, conflict resolvers
    $0.57, Inspectors $0.41, documentation reviewers $0.33, QA $0.09.
  - By change: CR-104 $1.47, CR-102 $1.31, CR-105 $0.76, CR-103 $0.68, CR-101 $0.38 (the
    Foreman's $3.91 apart).
- **Agents:** 59 under the Foreman: 11 Drivers, 1 QA driver, 47 workers.
- **Audit:** 439 of 440 checks passed (the audit as it is now, run on this batch).
- **Context:** no worker or Driver went above 38,136 tokens; the Foreman reached 154,397.

## For maintainers

- chantier 0.1.0, branch `live-eval` at 88f9c56 (before #8); Foreman on Opus 5.5, every other
  agent on Sonnet 5.5; Windows 11, Claude Desktop.
- The failed check: ``FAIL a1b24f385f (chantier-eval-docs-reviewer) starts with a `chantier <role>`
  prompt`` — CR-104's third Driver started the docs reviewer with a prompt of its own (finding 5).
- The operator once chained a merge that failed with the next order; it was held and sent after
  the real merge. The runbooks now say to merge alone.
