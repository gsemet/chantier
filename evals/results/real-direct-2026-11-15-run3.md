# real-direct, 2026-11-15, run 3

**Verdict:** passed with findings. Mode: parallel, direct. The 5 CRs were merged and the judge
passes every CR and `main` (6 pass, 0 fail, 0 not run). The audit failed 2 of its 555 checks, both
the operator's own slips (J14, J26), and left 1 unseen (J24, no `blocked` hand-back). Auto-fix was
on for the steering session until mid-run (see "Auto-fix"). Compared with run 1 (2026-11-12) on the
same sandbox base, the audit's own mistakes are gone and the cost is about the same.

## The run

| | |
| --- | --- |
| Campaign, run, date | real-direct, run 3, 2026-11-15 |
| PR prefix | `[eval 3 2026-11-15 real-direct]` |
| chantier at setup | 0.9.0, commit `fa97e7037e6d9dbae8fcc6870e07b0994d0eb21b`, with uncommitted changes |
| chantier now | the same commit |
| Sandbox base | `6e87a361c1b192e6d081c162f0cb2cc28bb72b25`; the workspace's root commit is the base |
| Batch | batch-01, mode parallel, steered by the Chief of Staff (direct), host claude |
| Models | chief-of-staff: claude-opus-5-5 (1) |
|  | coder: claude-sonnet-5-5 (6) |
|  | conflict-resolver: claude-sonnet-5-5 (2) |
|  | cr-driver: claude-sonnet-5-5 (5) |
|  | inspector: claude-sonnet-5-5 (10) |
|  | verifier: claude-sonnet-5-5 (25) |

## What was tested

The sandbox project `shelf` is a small reading list served on the web. Five frozen and specified
CRs ran in one **parallel** batch with no Foreman: delete-item, edit-item, status-filter, json-api
and stats-page. It had a $20 budget. The Chief of Staff steered the batch itself (direct mode) and
played the user: the go, every merge with `sandbox.py merge`, the pause, the audit and the close.
The session was a Claude Desktop Code session. Its sandbox base is the same as run 1's:
`6e87a361c1b192e6d081c162f0cb2cc28bb72b25` (both audits print it in their "The run" tables).
chantier moved from 0.8.0 (run 1) to 0.9.0 at `fa97e70`.

Not covered: Copilot, GitLab.

## What happened

The batch opened at 12:43:06 UTC and closed at 13:15:09. The PRs merged in this order: #12 CR-103
at 12:49:34, #13 CR-102 at 12:54:06, #15 CR-104 at 12:58:51, #16 CR-105 at 13:03:15, #14 CR-101 at
13:06:16. That is about 23 minutes from `open` to the last merge, as in run 1.

- **CR-103 status-filter** (PR 12) needed 1 round and merged first.
- **CR-102 edit-item** (PR 13) needed 1 round. After CR-103 merged it went back to its Driver with
  a `rebase:` note; the first description pass was `NOT VERIFIED` on stale heads in its evidence
  file (finding 4).
- **CR-104 json-api** (PR 15) needed 1 round and merged third.
- **CR-105 stats-page** (PR 16) needed 2 rounds. "Round 2" was started by a stray command with no
  Coder; the Verifier's `NOT VERIFIED` was on the PR body only.
- **CR-101 delete-item** (PR 14) was the costliest ($2.98) and needed 2 rounds. It was taken back
  twice (after CR-104 and after CR-105 merged) and rebased with conflicts once. It merged last.

Rounds: 2, 1, 1, 1, 2 for CR-101 to CR-105, 7 in all (run 1: 9). Nobody asked a question, no CR
was blocked, no force push was refused, and no budget was raised or dropped.

**Auto-fix.** The app's Auto-fix was **not off** at the start of the run. Two `ci-monitor-event`s
(merge conflicts on PR #14, heads f8651dc and 4b161ce) reached the steering session. It ignored
both, because CR-101 had a live Driver; the event's text asked it to "merge the base branch in
(never rebase or force-push)", which contradicts the batch's rebase flow. The parent session asked
it at about 13:02 to turn Auto-fix off and to record that it had been on from the start. At 13:03:07
it ran `mcp__ccd_pr__set_monitor {auto_fix:false, address_comments:false}` for PR #14 and the host
answered "Auto-fix is off for gsemet/chantier-eval-sandbox#14". The off state covers PR #14 only,
after CR-104 had merged and before CR-105 merged. The steering session also recorded that the
background had said Auto-fix was off for the session while the app showed it on.

**Messages.** No `ping`, and no refused send (J15). The steering session sent Drivers 7 messages
(rebase notes and takes back) and 1 to the parent session (Auto-fix turned off); all were
delivered.

**Heartbeat.** Armed once with `ScheduleWakeup` (1800 s) at 12:44:09 and stopped with `stop: true`
at 13:08:38, after `pause`. No timed wake fired; Driver hand-backs woke the session.

## Findings

1. **Auto-fix was on for the whole first half of the run.** The runbook asks the operator to turn
   it off before a campaign (`evals/README.md`), and the steering session reported "off" in the
   background while the app showed "on". Two conflict events reached the session; it ignored both,
   correctly. It matters because a session that obeyed would have pushed onto CR-101's Driver's
   branch mid-rebase. It is run 1's finding 2 again, with a way to turn it off now proven:
   `mcp__ccd_pr__set_monitor {auto_fix:false, address_comments:false}` per PR (retro point 1). The
   fix: `hosts/claude-code.md` ("Auto-fix events") records that call, and the eval setup turns
   Auto-fix off before the go.
2. **A steering session in direct mode labels its notes and its `asks` output with the Foreman.**
   Its `SendMessage` texts read `[foreman->driver CR-102] note ...` and `asks` printed
   `[foreman->chief-of-staff]`, in a batch with no Foreman. It matters because a reader of a
   Driver's transcript is told a Foreman exists. The fix: label by the actual steering role in
   direct mode (the label's source was not traced: the card text or the CLI).
3. **`cost --explain` and `cost --by cr` refuse on a paused batch without `--batch`.** Same as
   run 2's finding 6: `error: no running batch: run `chantier open` first; no batch closed yet`.
   The fix: the runbook says `--batch`, or the CLI picks the one paused batch.
4. **Stale SHAs in the evidence files make the first description pass `NOT VERIFIED` after a
   rebase (CR-101, CR-102, CR-105).** It matters because each is a Verifier run spent on a path
   that a rebase changed (retro point 3). The fix: the Driver or Verifier updates the heads in
   `before-after.md`.
5. **The Verifier cost $2.457 over 25 agents, about 10 of them re-verifications after a clean
   rebase.** It is 21% of the batch. The fix: carry the verdict over a clean rebase with an
   unchanged patch, as the long gate already is (3 carries this run; retro point 4).
6. **The board did not start:** `error: board not started: [WinError 10048]` (port in use). It is
   run 1's finding 13 again. The fix: pick a free port, or name the board that holds it (retro
   point 2).
7. **The audit's J14 and J26 FAILs are the operator's calls, not the product's.** J14: the rules
   were run through a shell variable (`$C rules`). J26: the brief was written with a shell
   heredoc (`python - <<'EOF' ...`) chained in one call, and the audit reads it as the steering
   session writing a file in the main checkout. Both clean checkouts matched the remote
   (717c217). It matters because a clean run exits 1. The fix: the operator calls the CLI plainly
   and writes the brief with the Write tool; `audit.py` may treat a heredoc to the planning
   folder as no breach.
8. **The preflight trial `git push --force-with-lease -u origin chantier/preflight-trial
   --dry-run` fails with `src refspec ... does not match any`**, as in run 2's finding 9, so it
   proves nothing about the rule. Run 1's findings are followed one by one below.

## Run 1's findings, one by one

| run 1 finding | run 3 |
| --- | --- |
| 1 "no CI" claims by Drivers | not seen: none of the 5 PR bodies (12 to 16) contains "no CI" |
| 2 Auto-fix fights the batch | recurred (finding 1) |
| 3 steering turns counted as grill turns | gone: grill is $0.05 (1 call) and steering is $3.39 (30%) |
| 4 audit flags the Verifier's detached worktree | gone: J3 passes 126 checks |
| 5 audit's C9 flags the report refresh | gone: C9 passes |
| 6 J14 timing slip | recurred as an operator slip (finding 7) |
| 7 a Verifier wrote outside its folders | not seen: J3 and J12 pass (43 checks) |
| 8 a rebase note raced a ready hand-back | not checked |
| 9 a CR that works while others merge pays for each | recurred: CR-101 cost $2.98 and was retaken twice |
| 10 byte-order marks | not checked |
| 11 description pass fails on a missing record | recurred as stale SHAs (finding 4) |
| 12 `status` shows a stale spend | not checked |
| 13 board did not start | recurred (finding 6) |

## Direct mode: the host lines this run proved

`hosts/claude-code.md` marks these unproved for direct mode; run 1 proved the first three.

- **A Driver's `SendMessage` to `main`:** seen working again. The five Drivers' hand-backs reached
  the steering session, and its seven messages to Drivers were delivered, resuming ended Drivers.
- **The heartbeat in the Chief of Staff's own session:** armed (12:44:09) and stopped after `pause`
  (13:08:38). A timed wake firing is still unproved: the batch finished inside the first 30
  minutes.
- **The `Chief of Staff, steering the batch` cost row:** seen, $3.390 (62 calls, 30%) at the
  audit. Run 1's understatement (finding 3 there) is gone.
- **A refused force push judged and run by the Chief of Staff:** not seen. No push was refused.
- **`order qa` refused while the batch runs:** not tried.
- **Newly seen:** `mcp__ccd_pr__set_monitor` turns Auto-fix off for one PR (finding 1). It does
  not turn it off for the session's other PRs.

## Scorecard

| id | rail | mark | evidence |
| --- | --- | --- | --- |
| C1 | `take` refused with no free slot | not seen | no refusal |
| C2 | `take` refused while `after` is unmet | not seen | no dependency |
| C3 | budget refusals | not seen | $11.52 of $20 |
| C4 | round limit refusal | not seen | at most 2 rounds |
| C5 | `gate` | seen, right | audit: 1 check |
| C6 | `verdict` bound to a clean head | not seen | no refusal |
| C7 | `handback ready` needs PR, gate and VERIFIED at the head | seen, right | audit: 1 check |
| C8 | `ship` | seen, right in part | each ready hand-back needed the recorded PR; no refusal |
| C9 | steering commands carry the epoch | seen, right | audit: 1 check (run 1's FAIL is gone) |
| C10 | the heartbeat | seen, right in part | armed, then stopped after `pause`; no timed wake |
| C11 | `release go` | not seen | no release |
| C12 | only the steering session merges | seen, right | audit: 6 checks |
| C13 | `order qa` refused while a direct batch runs | not seen | not tried |
| C14 | `pause` and `close` | seen, right | audit: 7 checks; `close` refused once (transcripts under 5 min) |
| C15 | `open` refused while a batch is open | not seen | not tried |
| C16 | merged CR folders | seen, right | audit: 5 checks |
| C17 | `take` of a ready CR needs `--note` | not seen | every take of a ready CR had its note |
| C18 | a release on `order confirm` | not seen | no release |
| C19 | `order drop` | not seen | no drop |
| C20 | a fix restarts the release | not seen | no release |
| J1 | agents' prompts | seen, right | audit: 192 checks |
| J2 | who starts whom | seen, right | audit: 49 checks |
| J3 | worker boundaries | seen, right | audit: 126 checks |
| J4 | Driver's worktree, rebase, lease push, explicit paths | seen, right | audit: 11 checks |
| J5 | draft, then ready on the default branch, prefix, CI green | seen, right | audit: 5 checks |
| J6 | Driver reads CI with the forge's CLI | seen, right | audit: 5 checks; no "no CI" claim |
| J7 | Verifier at the pushed head | seen, right | VERIFIED at each merged head; stale SHAs caught (finding 4) |
| J8 | `FIX-REQUIRED` on the body only is not a round | not seen | CR-105's body-only `NOT VERIFIED` was not a Coder round, but no Inspector body-only verdict was read |
| J9 | question to the user | not seen | no question |
| J10 | rebase after each merge in parallel | seen, right | every open PR got a `rebase:` note or a take back after each merge; `gh pr view 14 --json mergeable` was used (`UNKNOWN` once, `CONFLICTING` once) |
| J11 | refused force push | not seen | no refusal |
| J12 | `writes:` lines | seen, right | audit: 43 checks |
| J13 | `git status --porcelain` before reports | seen, right | audit: 1 check |
| J14 | rules, cleanup, retro, pause | seen, wrong | audit FAIL, the operator's `$C rules` (finding 7) |
| J15 | the host's message limit | seen, right | 8 sends, none refused; no `ping` |
| J16 | report format | not seen | not read against `status-layout.md` |
| J17 | context windows | seen, right | audit: 48 checks; peak Driver 123,512 tokens (CR-101) |
| J18 | a CR sent back has its PR turned to draft first | not seen | not read |
| J19 | escalation | not seen | no escalation |
| J20 | CR names | not seen | not read |
| J21 | state only through `$CHANTIER` | seen, right | audit: 49 checks |
| J22 | the steering session never codes or pushes | seen, right | audit: 1 check |
| J23 | release drafts | not seen | no release |
| J24 | blocked hand-back words | not seen | audit: 0 `blocked` hand-backs |
| J25 | a Driver's CI claim comes from the forge at the pushed head | not seen | not read (no "no CI" in the 5 PR bodies) |
| J26 | fast-forward of the main checkout after a merge | seen, wrong | audit FAIL: a heredoc by the steering session (finding 7); the workspace and the remote were both at 717c217 |

**Cost:** $11.518 over 506 model calls at the audit. The archive's `batch-01.json` says $11.91 at
the close, and the operator's note says $11.80; the three figures are from different moments and
were not reconciled. Nothing is "not measured".
**Steering share:** 29.4% (Chief of Staff $3.39 of $11.52).

## Numbers

- **Duration:** about 23 minutes from `open` (12:43:06 UTC) to the last merge (13:06:16); the
  close was at 13:15:09.
- **Cost total:** $11.52 at the audit (506 calls); $11.91 at the close per the archive; $11.80 per
  the operator. Budget $20. After `cost --explain`: $11.467 over 505 calls.
- **Cost by agent (`cost` at the audit):** Chief of Staff steering $3.390 (30%), its own subagent
  (the retro-critic) $0.386, CR Drivers $3.558, Verifiers $2.457, Inspectors $0.829, Coders
  $0.740, conflict-resolvers $0.158. Orchestration is 64% (63% after `--explain`).
- **Cost by CR (`cost --by cr`):** CR-101 $2.983, CR-102 $1.559, CR-104 $1.257, CR-105 $1.072,
  CR-103 $0.870, steering ("foreman" line) $3.776.
- **Outside the budget:** grill $0.05 (1 call); the Chief of Staff's whole session $1.64
  (context 224,242 tokens, 0 compactions).
- **Cache:** 0 timed calls after the cache expired; 0 CR Drivers restarted.
- **Agents started:** 48: 6 Coders, 2 conflict-resolvers, 5 CR Drivers, 10 Inspectors, 25
  Verifiers; the retro-critic ran outside the batch.
- **Rounds:** 2, 1, 1, 1, 2 for CR-101 to CR-105 (7 in all; run 1: 9).
- **Audit checks passed:** 553 of 555.
- **Steering share:** 29.4%.
- **Judge:** 6 pass, 0 fail, 0 not run.

| CR | PR | head judged | hidden tests | suite | result |
| --- | --- | --- | --- | --- | --- |
| CR-101 delete-item | 14 | 3aca423 | 5 passed | 64 passed | pass |
| CR-102 edit-item | 13 | 2673f63 | 5 passed | 45 passed | pass |
| CR-103 status-filter | 12 | 4d7915d | 6 passed | 40 passed | pass |
| CR-104 json-api | 15 | 4fc996a | 6 passed | 54 passed | pass |
| CR-105 stats-page | 16 | bedad4d | 4 passed | 57 passed | pass |
| main (5 CRs) | - | 717c217 | 26 passed | 85 passed | pass |

**Against run 1:** audit 553 of 555 (run 1: 630 of 636); cost $11.52 at the audit (run 1:
$11.55 corrected); steering share 29.4% (run 1: 29%); agents 48 (56); rounds 7 (9); judge 6 pass
in both. The cost row now prices steering without the grill misattribution, so no correction was
needed.

## For maintainers

chantier 0.9.0 at `fa97e7037e6d9dbae8fcc6870e07b0994d0eb21b`, with uncommitted changes at setup.
The failed audit checks, verbatim (J26's text is cut where the audit's line ends):

```text
- FAIL [J14] the steering session read the project's rules (`chantier rules`)
- FAIL [J26] after a merge it records, the steering session fast-forwarded the clean main checkout with `merge --ff-only --no-overwrite-ignore` only, or said why it did not, in a `main checkout:` note (the workspace is at 717c217, the remote's main at 717c217, and the steering session ran `python - <<'EOF' p='.agents/changes/4-batch/brief.md'...
```

The batch's retro is kept in the workspace's archive (`5-archives/batches/batch-01.md`); its four
kept points are findings 1, 4, 5 and 6. The sandbox is left as the run ended: 5 merged PRs and
`main` at `717c217`.
