# real-foreman, 2026-11-22, run 4

**Verdict:** passed, with findings. Mode: stack. All 5 CRs merged in one native stack merge, and the
judge passes all 6 heads (the 5 CRs and `main`). The audit failed 9 of its 473 checks (J3, J4,
J5 ×4, J12 ×2, J14) and left J24 unseen. Reading the evidence, J5 and J14 look like audit
misreadings of a native stack merge. J3, J4 and J12 point at agents and need a closer look
(findings 8 to 11). Run 2's merge blocker is gone: `sandbox.py merge 20` merged the whole stack in
one call. The judge ran every head, so run 2's finding 2 is fixed too.

## The run

| | |
| --- | --- |
| Campaign, run, date | real-foreman, run 4, 2026-11-22 |
| PR prefix | `[eval 4 2026-11-22 real-foreman]` |
| chantier at setup | 0.14.0, commit `be1794e7bfb78f1d4ac2ebfd61e8a52262de1639`, with uncommitted changes |
| chantier now | the same commit |
| Sandbox base | `85f41399606c56e92840818b2d863239450fead2`; the workspace's root commit is the base |
| Batch | batch-01, mode stack, steered by the Foreman, host claude |
| Models | foreman: claude-sonnet-5-5 (1) |
|  | coder: claude-sonnet-5-5 (5) |
|  | conflict-resolver: claude-sonnet-5-5 (3) |
|  | cr-driver: claude-sonnet-5-5 (5) |
|  | inspector: claude-sonnet-5-5 (11) |
|  | retro-critic: claude-opus-5-5 (1) |
|  | stack-driver: claude-sonnet-5-5 (2) |
|  | verifier: claude-sonnet-5-5 (14) |

## What was tested

The sandbox project `shelf` is a small reading list served on the web. Five frozen, specified CRs
ran in one batch in **stack** mode with a $20 budget: delete-item, edit-item, status-filter,
json-api and stats-page. A Foreman steered the batch from its own session. The operator (the Chief
of Staff's session, in forced Foreman mode) played the user: preflight, permission trials, the
go, the merge, the audit and the close. A stack Driver built the stack with `forge-stack`. It is
native GitHub stack #23 (an earlier #22 was replaced). The CRs' PRs are #19, #17, #18, #21 and #20.
The session ran on Claude Desktop (Claude Code).

Not covered: Copilot, GitLab, a release, a QA order.

## What happened

The batch opened at 18:12:36 UTC. The Foreman sent `ready` at epoch 1 with 3 slots taken. The PRs
opened from 18:52:04 to 18:58:47: #17 (CR-102), #18 (CR-103), #19 (CR-101), #20 (CR-105) and
#21 (CR-104). The stack merged at 19:06:40, about 54 minutes after `open`, and the batch closed
at 19:09:58.

- **CR-102 edit-item** (PR 17): 1 round, 1 long gate, at the bottom of the stack.
- **CR-103 status-filter** (PR 18): 1 round. It was restacked onto CR-102 and passed a second long
  gate.
- **CR-101 delete-item** (PR 19): 1 round. A conflict-resolver fixed it during the restack. `ship`
  refused it at first because it was not based on CR-103's head `6045e24`, yet the hand-back was
  accepted (finding 6). Its Driver's anomaly note was lost when its lease ended, so the Foreman
  recorded it (finding 5).
- **CR-104 json-api** (PR 21): 1 round. A conflict-resolver fixed it during the restack, then it
  passed a second long gate.
- **CR-105 stats-page** (PR 20): 1 round. Its gate was carried over a clean rebase.

**Merge.** The Foreman's ask A-2 `stack-ready-to-merge` said the stack was complete and mergeable
below `7af3da6`. `forge-stack show` agreed: "stack #23 ready to merge: open, 5 PRs in order, stack
complete". `uv run --no-project python evals/kit/sandbox.py merge 20` printed "merged PR #17 #18
#19 #21 #20 at 7af3da6 into main by rebase (one stack merge, merged)" (forge time
2026-11-22T19:06:40Z). The operator then recorded `order merged` for CR-102, CR-103, CR-101,
CR-104 and CR-105 (O-1 to O-5). The CLI removed the merged worktrees and branches and paused the
batch. The Foreman fast-forwarded the main checkout to `cce0a3e` (`uv.lock` unchanged), wrote the
retro (the critic kept 0 points and dropped 3) and sent `final`.

**Auto-fix.** The run's PRs are bound to the Foreman's session, not the operator's.
`get_status` on the Foreman's session showed `auto_fix` false, so there was nothing to turn off.
No `ci-monitor-event` arrived. The operator could not have turned it off anyway (finding 7).

**Messages.** No `ping` and no refused send (J15). The operator sent the Foreman 2 messages: the
start, and one message with the 5 `order merged` lines. Turns started only by a Foreman turn-end
notice ended with no tool call (J29). No budget was raised or dropped, and no question reached the
user.

**Heartbeat.** The archive counts 7 Foreman wakes. The heartbeat's arming and stop were not read
for this report.

## Findings

1. **`seat take` needs the session id as a positional argument.** `seat take --title ...` alone
   exits 1 with `error: seat take <session-id>`. It matters because the card's wording leads to the
   failing form. The fix: the card shows `seat take <session-id> --title ...`, or the CLI reads the
   id from the host when none is given.
2. **The evals README gives the operator's `$CHANTIER` as `uv run --locked --project ...`, but the
   skill's plugin mode says `uvx --from ... --skill ...`.** The operator used the skill's form. It
   matters because P10's rule matches only one form. The fix: the README defers to the skill.
3. **Under auto mode, `start_session` for the Foreman was refused by the classifier**
   ("[Destructive or Unwanted Actions]"). It started only after the real user wrote "Yes, start it".
   It matters because the runbook says nothing waits on the real user, which does not hold under
   auto mode. The fix: the runbook names this one confirmation, or the host card says the start
   needs the user's own word.
4. **`start_session` with context `fresh` needs a `background` of at least 80 characters.** The
   host card and the Foreman prompt template don't say so, so the first try was refused. The fix:
   the template carries a background long enough.
5. **A Driver's anomaly note was lost when its lease ended (CR-101).** The Foreman recorded it
   instead. It matters because notes are the run's evidence. The fix: `note` is accepted from a
   Driver whose lease just ended, or the hand-back carries the pending note.
6. **`ship` refused CR-101 because it was not based on CR-103's head `6045e24`, yet `handback
   ready` accepted it.** It matters because the two rails disagree on the same base check. The fix:
   `handback` applies `ship`'s stack-base check, or `ship` relaxes it the same way.
7. **The operator cannot turn Auto-fix off for the run's PRs.** They are bound to the Foreman's
   session, and `set_monitor` acts only on the calling session's own PR. It did no harm this run
   (`auto_fix` was false). The fix: the runbook says the Foreman's brief turns it off, or the
   operator only checks it.
8. **The audit's J5 fails on PRs merged through the native stack (4 FAILs).** PRs 18, 19, 21 and 20
   show as merged into the branch below them. That is how a native stack merge records them, while
   the commits reached `main` (`cce0a3e`). The fix: J5 accepts a lower stack branch as the base of a
   PR merged in a recorded stack merge.
9. **The audit's J14 says the steering session removed the merged worktrees before the pause.** It
   was the CLI's own cleanup inside `order merged`, which then paused the batch. The fix: J14 reads
   the cleanup in `order merged` as the steering session's, in order.
10. **J12: inspectors `a1c11b8308` (CR-105) and `adc22897e6` had no `writes:` line in their
    prompts.** The guard still applied, but the rail is that the line is there. The fix: the
    Driver's Inspector template always carries `writes:`; read the two prompts to see which form
    dropped it.
11. **J3 and J4 on CR Drivers.** `a44413147c` (CR-101) failed "writes no code itself: ['']", which
    is an empty path and looks like a parse artifact in the audit. `aff1ba146b` failed "stages
    explicit paths only". The fix: read both transcripts. J3 is likely an audit fix for an empty
    path, and J4 may be a real `git add -A` or `git add .`.
12. **The preflight trial `git push --force-with-lease -u origin chantier/preflight-trial
    --dry-run` still fails with `src refspec chantier/preflight-trial does not match any`.** This
    is run 2's finding 9 again. Per the card, a command error counts as a pass of the permission
    trial. The fix: push `HEAD:refs/heads/chantier/preflight-trial`.
13. **P10 warned about 3 missing rules** (force-with-lease push, `gh pr close`, `gh pr reopen`)
    and about out-of-date broad rules in `~/.claude/settings.json`. These were left to the user, and
    every trial ran with no prompt. Recorded, no action.
14. **The watcher's "forge saw merged" lines arrived after the orders were already recorded.** It
    matters little, but the watcher is meant to bring the merge to the steering session. The fix:
    none needed if this is by design; otherwise poll the forge sooner after a stack merge.

## Scorecard

| id | rail | mark | evidence |
| --- | --- | --- | --- |
| C1 | `take` refused with no free slot | not seen | no refusal |
| C2 | `take` refused while `after` is unmet | not seen | no refusal |
| C3 | budget refusals | not seen | $9.88 of $20 |
| C4 | round limit refusal | not seen | 1 round each |
| C5 | `gate` | seen, right | audit: 1 check |
| C6 | `verdict` bound to a clean head | not seen | no refusal |
| C7 | `handback ready` needs PR, gate and VERIFIED at the head | seen, right | audit: 1 check; CR-105's gate carried |
| C8 | `ship` | seen, right in part | refused CR-101 off CR-103's head; the hand-back disagreed (finding 6) |
| C9 | steering commands carry the epoch | seen, right | audit: 1 check |
| C10 | the heartbeat | not read | 7 Foreman wakes in the archive |
| C11 | `release go` | not seen | no release |
| C12 | only the steering session merges | seen, right | audit: 8 checks; one `sandbox.py merge 20` |
| C13 | `order qa` refused while a direct batch runs | not seen | Foreman batch |
| C14 | `pause` and `close` | seen, right | audit: 7 checks |
| C15 | `open` refused while a batch is open | not seen | not tried |
| C16 | merged CR folders | seen, right | audit: 5 checks |
| C17 | `take` of a ready CR needs `--note` | not seen | no refusal |
| C18 | a release on `order confirm` | not seen | no release |
| C19 | `order drop` | not seen | no drop |
| C20 | a fix restarts the release | not seen | no release |
| C21 | `order merged` stops a running gate | not seen | no gate ran at the merge |
| J1 | agents' prompts | seen, right | audit: 163 checks (run 2's retro-critic FAIL is gone) |
| J2 | who starts whom | seen, right | audit: 42 checks |
| J3 | worker boundaries | seen, wrong | audit FAIL on cr-driver `a44413147c`, empty path (finding 11) |
| J4 | Driver's worktree, rebase, lease push, explicit paths | seen, wrong | audit FAIL on cr-driver `aff1ba146b` (finding 11) |
| J5 | draft, ready on the default branch, prefix, CI green | seen, right | 4 audit FAILs read as the native stack's bases (finding 8) |
| J6 | Driver reads CI with the forge's CLI | seen, right | audit: 5 checks |
| J7 | Verifier at the pushed head | seen, right | 14 Verifiers; the judge passes every head |
| J8 | `FIX-REQUIRED` on the body only is not a round | not seen | 1 round each |
| J9 | question to the user | not seen | no `blocked question:` |
| J10 | rebase after each merge in parallel | not seen | stack mode |
| J11 | refused force push | not seen | no refusal |
| J12 | `writes:` lines | seen, wrong | audit FAIL on inspectors `a1c11b8308` and `adc22897e6` (finding 10) |
| J13 | `git status --porcelain` before reports | seen, right | audit: 1 check |
| J14 | rules, cleanup, retro, pause | seen, right | audit FAIL read as the CLI's cleanup in `order merged` (finding 9) |
| J15 | the host's message limit | seen, right | 2 operator sends, none refused; no `ping` |
| J16 | report format | not seen | not read against `status-layout.md` |
| J17 | context windows | seen, right | audit: 41 checks; Foreman peak 240,950 tokens |
| J18 | a CR sent back has its PR turned to draft first | not seen | not read |
| J19 | escalation | not seen | no escalation |
| J20 | CR names | not seen | not read |
| J21 | state only through `$CHANTIER` | seen, right | audit: 42 checks |
| J22 | the steering session never codes or pushes | seen, right | audit: 1 check |
| J23 | release drafts | not seen | no release |
| J24 | blocked hand-back words | not seen | 0 `blocked` hand-backs |
| J25 | a Driver's CI claim comes from the forge at the pushed head | not seen | Driver notes not read for it |
| J26 | fast-forward of the main checkout after a merge | seen, right | audit: 1 check; `cce0a3e` |
| J27 | pipeline job as the long gate | not seen | no such rule |
| J28 | `git merge-tree` check in a parallel Foreman batch | not seen | stack mode |
| J29 | a turn started by a Foreman turn-end notice ends at once | seen, right | operator replied "Noted." with no tool call |

**Cost:** $9.883 over 526 model calls at the audit; $9.88 at the close (the archive's
`batch-01.md`). Every call was priced.
**Steering share:** 21.7% (Foreman $2.15 of $9.88, `cost` at the audit). With its own subagent,
as the archive counts it, the Foreman is $2.48 (25%).

## Numbers

- **Duration:** about 54 minutes from `open` (18:12:36 UTC) to the stack merge (19:06:40). The
  close was at 19:09:58.
- **Cost total:** $9.88 of a $20 budget (audit: $9.883 over 526 calls).
- **Cost by agent (`cost` at the audit):**
  - Foreman $2.149 (22%), and its own subagent (the retro-critic) $0.331.
  - CR Drivers $3.058 (31%), stack Drivers $1.135 (12%).
  - Verifiers $1.524, Coders $0.750, Inspectors $0.729, conflict-resolvers $0.207.
  - Orchestration (steering + Drivers) is 68%.
- **Cost by CR (`cost --by cr`):** Foreman $2.480, CR-101 $1.621, CR-104 $1.439, CR-103 $1.153,
  other (stack Driver) $1.135, CR-105 $1.050, CR-102 $1.005.
- **Archive split:** Foreman $2.48 (25%), Drivers $4.19 (42%), workers $3.21 (33%). The Foreman had
  7 wakes, with context 197,752 tokens on average and 240,950 at its peak.
- **Outside the budget:** the Chief of Staff steering the batch $1.27 (31 calls), grill $0.39,
  whole session $4.09 (the archive at the close).
- **Cache:** 0 timed calls after the cache expired; no Driver compaction.
- **Agents started:** 41 under the Foreman: 5 Coders, 3 conflict-resolvers, 5 CR Drivers,
  11 Inspectors, 2 stack Drivers, 14 Verifiers and the retro-critic (Opus).
- **Rounds:** 1 for every CR.
- **Audit checks passed:** 464 of 473.
- **Judge:** 6 pass, 0 fail, 0 not run.

| CR | PR | head judged | hidden tests | suite | result |
| --- | --- | --- | --- | --- | --- |
| CR-101 delete-item | 19 | e91ba54 | 5 passed | 58 passed | pass |
| CR-102 edit-item | 17 | 28cb66d | 5 passed | 43 passed | pass |
| CR-103 status-filter | 18 | 6045e24 | 6 passed | 51 passed | pass |
| CR-104 json-api | 21 | ed5640a | 6 passed | 68 passed | pass |
| CR-105 stats-page | 20 | 7af3da6 | 4 passed | 71 passed | pass |
| main (5 CRs) | - | cce0a3e | 26 passed | 93 passed | pass |

## For maintainers

chantier 0.14.0 at `be1794e7bfb78f1d4ac2ebfd61e8a52262de1639`, with uncommitted changes at setup.
The failed audit checks, verbatim:

```text
- FAIL [J12] a1c11b8308 (inspector) prompt holds a `writes:` line (the plugin guards its writes)
- FAIL [J3] a44413147c (cr-driver) writes no code itself: ['']
- FAIL [J12] adc22897e6 (inspector) prompt holds a `writes:` line (the plugin guards its writes)
- FAIL [J4] aff1ba146b (cr-driver) stages explicit paths only
- FAIL [J14] the steering session removed the merged CRs' worktrees before the pause
- FAIL [J5] CR-101 PR 19: title starts with the prefix, no auto-merge, checks green at its head, merged (if merged) into the default branch: merged into chantier/batch-01/cr-103-filter-the-list-by-status, not main
- FAIL [J5] CR-103 PR 18: title starts with the prefix, no auto-merge, checks green at its head, merged (if merged) into the default branch: merged into chantier/batch-01/cr-102-edit-an-item, not main
- FAIL [J5] CR-104 PR 21: title starts with the prefix, no auto-merge, checks green at its head, merged (if merged) into the default branch: merged into chantier/batch-01/cr-101-delete-an-item, not main
- FAIL [J5] CR-105 PR 20: title starts with the prefix, no auto-merge, checks green at its head, merged (if merged) into the default branch: merged into chantier/batch-01/cr-104-read-the-items-as-json, not main
```

The audit exited 1 on these FAILs. The batch's retro is kept in the workspace's archive
(`5-archives/batches/batch-01.md`), where the critic dropped all 3 points. The sandbox is left as
the run ended: 5 merged PRs, stack #23 merged, and `main` at `cce0a3e`.
