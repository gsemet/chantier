# claude-full, 2026-11-04

**Verdict:** passed with findings. All eight changes ended as expected and the release went out,
but the host cut the Foreman off from the operator, and the run needed the user to write in the
Foreman's session twice. The red CI path was not exercised.

## What was tested

chantier was asked to make six small changes to `tasks-cli`, a to-do list program, then to release
v0.2.0 by the project's own procedure. Three changes started together and three were added on the
way. During the run, the user changed one request, answered two questions, dropped one change,
merged each pull request, edited the release notes and approved the irreversible steps.

## What happened

- **CR-101, add a priority to tasks.** Built in one round, merged first.
- **CR-102, a crash on an unknown task number.** The user asked for the error on the error stream
  while the Driver worked; done. It went back to a Driver twice to rebase after merges, on its own
  the second time, and was merged.
- **CR-103, a JSON output for the list.** Built in one round. A QA agent found nothing. Rebased
  after merges, then merged.
- **CR-105, a delete command.** Added during the run, built in one round, merged. Its CI was green
  on the first run: the coder met the hidden contract test, so no red CI happened.
- **CR-106, a CSV export.** Added during the run. The Driver stopped to ask which columns; a new
  Driver built it with the answer, and it was merged after a rebase.
- **CR-107, a stats command.** Added during the run. The project's style reviewer demanded French
  output, which the specification forbids. The Driver asked the user instead of going on, and the
  user dropped it.
- **CR-104, the release.** It waited for all the others. Its first attempt failed at the heavy
  check, as planned (`tasks --version` did not exist), and nothing irreversible had been done.
- **CR-108, the fix for the release.** Built in one round, then merged by the CLI under the user's
  grant, after the user confirmed that grant in the Foreman's session (finding 2).
- **CR-104 again.** The second attempt passed the check. The release notes kept the user's line,
  which reached `CHANGELOG.md`. The pull request was merged, then the tag `v0.2.0` was pushed, each
  on its own approval. It ended with a retrospective.

## Findings

1. **The host silenced the Foreman after 10 messages.** A session stops sending to other Desktop
   sessions after 10 messages until someone types in it, and nobody types in a detached Foreman. It
   hit the limit at `ok O-9`, early in the run. From then on no `ok`, no `ask ready`, no question
   and no refusal reached the operator, who sat waiting: 13 of the run's 14.6 hours went that way.
   A normal batch will hit this too. To do: send the Foreman only the `ask` lines (the `ok` lines
   repeat what `status` shows), and have the Chief of Staff watch `status` rather than wait.
2. **The auto-mode classifier refused a merge the user had allowed.** The Foreman ran `chantier
   merge CR-108` under the grant and got `[Merge Without Review]`: the grant came from the Chief of
   Staff, and nothing in its session showed the user's word. It stopped correctly, but could not
   say so (finding 1). The merge passed once the user wrote in its session. Fixed on the branch
   `foreman-merges-release`: the Foreman merges both the fixes and the release PR, and a refused
   merge goes up once to the Chief of Staff, who holds the user's word. Not yet tried on a real
   classifier.
3. **The Foreman refused an order.** It would not record `order approve` for the release PR and
   the tag: two irreversible actions, ordered by the Chief of Staff, not by the user. The caution is
   sound, but `foreman.md` tells it to decide nothing, and approvals are meant to arrive this way.
   As it stands, an approval relayed by the Chief of Staff may not be enough. To do: decide how the
   user's word reaches the Foreman, and write it in the role.
4. **An approval covers one `go`, whatever it says.** The driver asked for "merge the PR, then push
   the tag" in one go. The approval named both, the merge spent it, and the tag had to be approved
   again. To do: ask for one action at a time, or let one approval name several.
5. **A Driver again wrote its own worker prompts.** CR-103's Driver started its coder, inspector and
   verifier with prompts of its own, so their contract did not reach them. This was finding 5 of the
   previous run: the fix did not hold. To do: find why, starting from that Driver's transcript.
6. **The red CI path is still unproved.** All 11 CI runs were green. To do: make the hidden contract
   something a coder cannot meet by reading the specification.
7. **The round limit is still unproved.** CR-107's Driver asked at once, which the runbook allows, so
   no CR reached the limit.
8. **The release driver asked for a review the runbook did not plan.** `RELEASING.md` has a
   maintainer review the notes, so it stopped until told they were reviewed, though the user had
   already edited them. The stop is right; the runbook should expect it.
9. **The release could have failed sooner.** The retrospective proposes running the heavy check on
   `main` in CI, so that a release CR does not start on a failing project.
10. **An eval is too slow to run this way.** Work took about an hour; the rest was waiting. Each
    stop above needed a person. Evals now keep the Foreman attached to the operator (see the
    [README](../README.md)); whether the limit of finding 1 spares an attached session is unknown.

## Numbers

- **Duration:** 14 h 40 (22:17 UTC on 2026-11-03 to 12:57 UTC on 2026-11-04), about an hour of it
  working.
- **Cost:** $8.86 in all, for a budget of $25.
  - By role: Foreman $3.78, Drivers $1.81, verifiers $0.68, coders $0.59, Release drivers $0.46,
    documentation reviewers $0.39, conflict resolvers $0.38, Inspectors $0.36.
  - By change: CR-102 $1.18, CR-106 $0.83, CR-103 $0.76, CR-108 $0.58, CR-101 $0.49, CR-105 $0.48,
    CR-104 $0.46, CR-107 $0.31 (the Foreman's $3.78 apart).
  - An idle heartbeat cost about $0.06.
- **Agents:** 65 under the Foreman: 12 Drivers, 5 Release drivers, 1 QA driver, 47 workers.
- **Audit:** 483 of 486 checks passed.

## For maintainers

- chantier 0.1.0, branch `release-driver`, at d96530a when the batch started and 3bfc5bb from
  22:26 UTC on: the commit landed during the run, and the plugin is read live. Foreman and every
  other agent on Sonnet 5.5, operator on Opus 5.5; Windows 11, Claude Desktop.
- The failed checks, all from CR-103's Driver (finding 5):
  ``FAIL a3cdc3965c (chantier:coder) starts with a `chantier <role>` prompt``,
  ``FAIL a43dca2b66 is told to read worker.md``,
  ``FAIL aa80425603 (chantier:inspector) starts with a `chantier <role>` prompt``.
- The operator was resumed after a night's stop, and first said no operator session existed: it was
  the operator itself. It approved the merge and the tag from the runbook, without the user's own
  word on them; the Foreman was right to wait for it. The user then confirmed both.
- The Release driver merged PR 7 itself, under the old flow, with no refusal, once the user had
  confirmed in the Foreman's session.
