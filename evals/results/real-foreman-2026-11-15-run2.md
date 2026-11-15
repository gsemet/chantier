# real-foreman, 2026-11-15, run 2

**Verdict:** passed with findings. Mode: stack. The 5 CRs were merged. The judge passes the 2 heads
it could reach (CR-101 and `main`) and could not run the other 4 CRs. The audit failed 1 of its 514
checks (J1, on the retro-critic's prompt) and left 1 check unseen. The kit's merge script could not
merge a PR of a native stack, so the operator merged with a fix branch's script. Whether Auto-fix
was off for this run is not recorded (see "What happened").

## The run

| | |
| --- | --- |
| Campaign, run, date | real-foreman, run 2, 2026-11-15 |
| PR prefix | `[eval 2 2026-11-15 real-foreman]` |
| chantier at setup | 0.9.0, commit `fa97e7037e6d9dbae8fcc6870e07b0994d0eb21b`, with uncommitted changes |
| chantier now | the same commit |
| Sandbox base | `6e87a361c1b192e6d081c162f0cb2cc28bb72b25`; the workspace's root commit is the base |
| Batch | batch-01, mode stack, steered by the Foreman, host claude |
| Models | foreman: claude-sonnet-5-5 (1) |
|  | chantier:retro-critic: claude-opus-5-5 (1) |
|  | coder: claude-sonnet-5-5 (6) |
|  | conflict-resolver: claude-sonnet-5-5 (3) |
|  | cr-driver: claude-sonnet-5-5 (6) |
|  | inspector: claude-sonnet-5-5 (12) |
|  | stack-driver: claude-sonnet-5-5 (2) |
|  | verifier: claude-sonnet-5-5 (15) |

## What was tested

The sandbox project `shelf` is a small reading list served on the web. Five frozen and specified
CRs ran in one batch in **stack** mode: delete-item, edit-item, status-filter, json-api and
stats-page. It had a $20 budget. A Foreman steered the batch from its own session; the operator
(the Chief of Staff's session) played the user: the go, the merges, the pause, the audit and the
close. A stack Driver built the stack with `forge-stack` (a native GitHub stack, PR #11 as the
forge numbered it; the five CRs' PRs are 8, 6, 7, 9 and 10). The session ran on Claude Desktop
(Claude Code).

Not covered: Copilot, GitLab.

## What happened

The batch opened at 10:51:59 UTC. The PRs were created from 10:55 to 11:01 and merged bottom up
from 11:17:31 to 11:20:06: PR 8 (CR-101), 6 (CR-102), 7 (CR-103), 9 (CR-104), 10 (CR-105). The
last merge came about 28 minutes after `open`; the batch closed at 11:28:00.

- **CR-101 delete-item** (PR 8) needed 2 rounds. Round 1 got a real `FIX-REQUIRED` on the code,
  and a `NOT VERIFIED` on a PR body with `<sha7>` placeholders. A missing "Human decisions"
  section was flagged on the body alone, which does not count as a round.
- **CR-102 edit-item** (PR 6) needed 1 round. A Driver note says the Inspector's reply was not
  parseable JSON; the Driver read the reply instead of restarting the Inspector.
- **CR-103 status-filter** (PR 7) needed 1 round, with a `FIX-REQUIRED` on the body only (a
  missing section).
- **CR-104 json-api** (PR 9) needed 1 round, with the same body-only `FIX-REQUIRED`. The restack
  needed a conflict-resolver, an Inspector and a Verifier again.
- **CR-105 stats-page** (PR 10) needed 1 round. It was restacked too, handed back blocked once
  with `waits: CR-104's new head ...`, and retaken after the stack was rebuilt.

All five CRs were taken from `main` at once, so the stack was built afterwards. `forge-stack
create` was refused by the forge with a 422 on its first try ("Pull requests must form a stack,
where each PR's base ref is the previous PR's head ref"). A second stack take followed, after
three restack rebases. The forge's restack replaced the heads the CLI had recorded, which is why
the judge could not find 4 of them (finding 2).

**Merge.** `sandbox.py merge 8` exited 4: `gh pr merge` is refused for a PR in a native stack
("must be merged using the asynchronous merge REST API"), and nothing merged. The batch stayed
blocked at the Foreman's ask A-1 `stack-ready-to-merge` from 11:14 to 11:17 while the steering
session asked the user how to go on. On the user's word every merge then used the fix branch's
script (`chantier/fix-sandbox-stack-merge`, PR #224 per the steering note; it was not on `main`),
which calls `PUT .../pulls/<n>/merge-async`. Each bottom merge restacks the PRs above and reruns
their CI. The first `merge 7` was refused by the script's guard ("PR #7's checks are not all green
at its head 59edd1f: test=pending"); 7, 9 and 10 merged after `gh pr checks <n> --watch` (10 to
20 s each). Heads at merge: 0319545, 93a906c, 59edd1f, 1f29cde, 3900c46. The Foreman
fast-forwarded the main checkout twice (22da32d, then 002a1dc).

**Auto-fix.** The operator did not record Auto-fix's state for this run. No `ci-monitor-event`
and no mention of Auto-fix is in the operator's or the Foreman's transcripts. Whether Auto-fix was
off is not verified, and no Auto-fix event is seen.

**Messages.** No `ping`, and no refused send (J15). The Foreman sent 4 messages to the operator
(ready, ask A-1, "O-1, O-2 handled", the final) and 3 to Drivers. The operator sent the Foreman 2
(O-1 and O-2, then O-3 to O-5). No budget was raised or dropped.

**Heartbeat.** Armed with `ScheduleWakeup` (1800 s, twice) and stopped with `stop: true` after the
retro. No timed wake fired: the batch ended inside the first interval.

## Findings

1. **`sandbox.py merge` cannot merge a PR of a native stack.** `gh pr merge` is refused for such
   a PR, so `merge 8` exited 4 and nothing merged. It matters because stack mode is a campaign
   mode: the operator was blocked for about 3 minutes, then merged with a branch not on `main`.
   The fix: bring PR #224's `merge-async` route into the kit, with its guard that the checks are
   green at the head (it rightly refused `merge 7` while `test` was pending).
2. **The judge cannot run a CR whose recorded head the forge's restack replaced (4 of 6 "not
   run").** The recorded heads (3f60a08, 194525b, 2eb57ae, 881a963) are not on the origin. The
   judge printed the PR's real head each time (93a906c, 59edd1f, 1f29cde, 3900c46). It matters
   because the judge is the campaign's proof that each CR works; this run proves 2 of 6 lines.
   The fix: when the recorded head is gone, the judge uses the PR's head at merge, which it
   already prints.
3. **`handback` prints "PR in draft ... waits on main" for a stack CR whose PR is already out of
   draft.** On CR-102 `ship` recorded `draft=False` at 10:58:26 and the CLI line came one second
   later. It matters because a Foreman reading it may hold a CR that is done (retro point 1). The
   fix: `handback` reads the draft state from the forge, as `ship` now does.
4. **In stack mode every CR starts on `main` and is restacked afterwards.** That cost three
   restack rebases, a conflict-resolver, an Inspector and a Verifier on each of CR-104 and CR-105,
   the forge's 422, a second stack take and CR-105's retake. It matters because stack mode pays
   for rebases as parallel mode does (retro point 2). The fix: start each CR on the previous CR's
   branch.
5. **PR bodies reach the Inspector or Verifier with a missing section or placeholders.**
   `FIX-REQUIRED` for a missing "Human decisions" section on CR-101, CR-103 and CR-104;
   `NOT VERIFIED` on CR-101 for `<sha7>` placeholders. It matters because each is an inspection or
   a verification spent on text (retro point 3). The fix: lint the body before the first
   Inspector.
6. **`cost` refuses on a paused batch without `--batch`.** After `pause` it answered `error: no
   running batch: run `chantier open` first; no batch closed yet` (exit 2); with `--batch
   batch-01` it ran. It matters because the audit step comes after `pause`. The fix: the runbook
   says `--batch`, or the CLI picks the one paused batch.
7. **The write guard refused a shell write that names the allowed folder as `/c/...`.** Coder
   `a86c0e1704` (CR-104) wrote `/c/Users/.../104-json-api/work/coder/r1.md` and the guard refused
   it as outside the folders the agent may write in, though its list held the same folder as
   `C:/Users/.../104-json-api`. It matters because a legitimate write is refused on Windows when
   the shell uses the POSIX form of a path. The fix: the guard normalizes `/c/` to `C:/` before it
   compares.
8. **Drivers pass `'gate long'` to `chantier phase` and the CLI refuses it (5 or more calls).**
   The usage message lists the choices, so each refusal cost a call. The fix: a card line, or the
   CLI's help, names the accepted value.
9. **The preflight trial `git push --force-with-lease -u origin chantier/preflight-trial
   --dry-run` fails with `src refspec chantier/preflight-trial does not match any`.** No such
   local branch exists. It failed the same way in run 3. It matters because the trial is what
   P10 relies on to prove the push rule. The fix (to confirm): the trial pushes
   `HEAD:refs/heads/chantier/preflight-trial`.
10. **A Verifier's write to the host's scratchpad was refused by the guard.** Verifier
    `a1e1ed3419` wrote a probe script outside its folders and the guard refused it. Run 1's
    finding 7 did not recur as a breach. No action; recorded because J3 and J12 held.
11. **The audit's J1 fails on the retro-critic's prompt (1 FAIL).** The prompt starts `chantier
    retro-critic for the Chief of Staff, in the project ...` and names its card. The cause of the
    FAIL was not found. It matters because the audit exits 1 on a run that did nothing wrong. The
    fix: read `audit.py`'s J1 for a retro-critic started in a Foreman's batch.
12. **`status` without `--refresh` showed "spent $7.43 of $20" at 11:04 and the same at 11:20**,
    while `heartbeat` lines moved. It is run 1's finding 12 again. The fix: print the age of the
    figure.
13. **`close` was refused twice (exit 2)** because transcripts, the retro-critic's included, had
    been written less than 5 minutes earlier. The rail works; the runbook could say to wait.

## Scorecard

| id | rail | mark | evidence |
| --- | --- | --- | --- |
| C1 | `take` refused with no free slot | not seen | no refusal |
| C2 | `take` refused while `after` is unmet | not seen | no refusal |
| C3 | budget refusals | not seen | $10.28 of $20 |
| C4 | round limit refusal | not seen | CR-101 used 2 rounds |
| C5 | `gate` | seen, right | audit: 1 check; 9 gate events |
| C6 | `verdict` bound to a clean head | not seen | no refusal |
| C7 | `handback ready` needs PR, gate and VERIFIED at the head | seen, right | audit: 1 check; 5 CRs |
| C8 | `ship` | seen, right | it recorded each PR and head; its draft wording is finding 3 |
| C9 | steering commands carry the epoch | seen, right | audit: 1 check |
| C10 | the heartbeat | seen, right in part | armed twice, stopped after the retro; no timed wake fired |
| C11 | `release go` | not seen | no release |
| C12 | only the steering session merges | seen, right | audit: 9 checks |
| C13 | `order qa` refused while a direct batch runs | not seen | stack mode |
| C14 | `pause` and `close` | seen, right | audit: 7 checks; `close` refused twice before it passed (finding 13) |
| C15 | `open` refused while a batch is open | not seen | not tried |
| C16 | merged CR folders | seen, right | audit: 5 checks |
| C17 | `take` of a ready CR needs `--note` | not seen | no refusal |
| C18 | a release on `order confirm` | not seen | no release |
| C19 | `order drop` | not seen | no drop |
| C20 | a fix restarts the release | not seen | no release |
| J1 | agents' prompts | seen, wrong | audit FAIL on retro-critic `a609474ff1` (finding 11) |
| J2 | who starts whom | seen, right | audit: 45 checks |
| J3 | worker boundaries | seen, right | audit: 107 checks; the guard refused a Verifier's scratchpad write (finding 10) |
| J4 | Driver's worktree, rebase, lease push, explicit paths | seen, right | audit: 16 checks; stack-driver `a5f5cf3e45` "pushes with a lease or a first upstream" is NOT SEEN |
| J5 | draft, then ready on the default branch, prefix, CI green | seen, right | audit: 5 checks |
| J6 | Driver reads CI with the forge's CLI | seen, right | audit: 6 checks |
| J7 | Verifier at the pushed head | seen, right | VERIFIED at each merged CR's head; a `NOT VERIFIED` caught `<sha7>` placeholders (finding 5) |
| J8 | `FIX-REQUIRED` on the body only is not a round | seen, right | CR-101, CR-103 and CR-104 body-only; CR-101's code `FIX-REQUIRED` made round 2 |
| J9 | question to the user | not seen | no `blocked question:` |
| J10 | rebase after each merge in parallel | not seen | stack mode; restacks went through the stack Driver and the forge |
| J11 | refused force push | not seen | no refusal |
| J12 | `writes:` lines | seen, right | audit: 36 checks; finding 7 is the guard's path form |
| J13 | `git status --porcelain` before reports | seen, right | audit: 1 check |
| J14 | rules, cleanup, retro, pause | seen, right | audit: 2 checks |
| J15 | the host's message limit | seen, right | 7 Foreman and 2 operator sends to the Foreman, none refused; no `ping` |
| J16 | report format | not seen | the Foreman's reports were not read against `status-layout.md` |
| J17 | context windows | seen, right | audit: 45 checks; the Foreman peaked at 209,051 tokens |
| J18 | a CR sent back has its PR turned to draft first | not seen | not read for the restacks |
| J19 | escalation | not seen | no escalation |
| J20 | CR names | not seen | not read |
| J21 | state only through `$CHANTIER` | seen, right | audit: 46 checks |
| J22 | the steering session never codes or pushes | seen, right | audit: 1 check |
| J23 | release drafts | not seen | no release |
| J24 | blocked hand-back words | seen, right | audit: 1 check; CR-105's `waits: CR-104's new head ...` |
| J25 | a Driver's CI claim comes from the forge at the pushed head | seen, right | CR-101's note "gh pr checks 8 at 0319545: test pass"; the other Drivers' notes were not all read |
| J26 | fast-forward of the main checkout after a merge | seen, right | audit: 1 check; 22da32d, then 002a1dc |

**Cost:** $10.282 over 501 model calls at the audit; $10.28 at the close (the archive's
`batch-01.json`). Every call was priced; nothing is "not measured".
**Steering share:** 20.4% (Foreman $2.10 of $10.28).

## Numbers

- **Duration:** about 28 minutes from `open` (10:51:59 UTC) to the last merge (11:20:06); the
  close was at 11:28:00.
- **Cost total:** $10.28 of a $20 budget (audit: $10.282 over 501 calls).
- **Cost by agent (`cost` at the audit):** Foreman $2.101 (20%), the Foreman's own subagent (the
  retro-critic) $0.407, CR Drivers $3.060, stack Drivers $0.722, Verifiers $1.787, Inspectors
  $1.136, Coders $0.811, conflict-resolvers $0.258. Orchestration (steering + Drivers) is 61%.
- **Cost by CR (`cost --by cr`):** Foreman $2.508, CR-104 $1.628, CR-105 $1.562, CR-102 $1.324,
  CR-101 $1.278, CR-103 $1.261, other (stack Driver) $0.722.
- **Outside the budget:** the Chief of Staff steering the batch $2.12 ($2.55 once `cost
  --explain` ran later), grill $0.21, whole session $3.91 ($4.34 later; the archive says $2.88 and
  $4.67 at the close).
- **Cache:** 0 timed calls after the cache expired; 1 CR Driver restarted on a CR that already had
  one.
- **Agents started:** 45: 6 Coders, 3 conflict-resolvers, 6 CR Drivers, 12 Inspectors, 2 stack
  Drivers, 15 Verifiers and the retro-critic (Opus).
- **Rounds:** CR-101 2, the others 1.
- **Audit checks passed:** 513 of 514.
- **Steering share:** 20.4%.
- **Judge:** 2 pass, 0 fail, 4 not run.

| CR | PR | head judged | hidden tests | suite | result |
| --- | --- | --- | --- | --- | --- |
| CR-101 delete-item | 8 | 0319545 | 5 passed | 39 passed | pass |
| CR-102 edit-item | 6 | 3f60a08 (PR head 93a906c) | - | - | not run |
| CR-103 status-filter | 7 | 194525b (PR head 59edd1f) | - | - | not run |
| CR-104 json-api | 9 | 2eb57ae (PR head 1f29cde) | - | - | not run |
| CR-105 stats-page | 10 | 881a963 (PR head 3900c46) | - | - | not run |
| main (5 CRs) | - | 002a1dc | 26 passed | 92 passed | pass |

## For maintainers

chantier 0.9.0 at `fa97e7037e6d9dbae8fcc6870e07b0994d0eb21b`, with uncommitted changes at setup.
The failed audit check, verbatim:

```text
- FAIL [J1] a609474ff1 (chantier:retro-critic) starts with a `chantier <role>` prompt
```

The audit exited 1 on this FAIL. The batch's retro is kept in the workspace's archive
(`5-archives/batches/batch-01.md`); its three kept points are findings 3, 4 and 5. The sandbox is
left as the run ended: 5 merged PRs and `main` at `002a1dc`.
