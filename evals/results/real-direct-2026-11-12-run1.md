# real-direct, 2026-11-12, run 1

**Verdict:** passed with findings. The 5 CRs were merged and the judge passes every CR and `main`.
The audit failed 6 of its 636 checks: 4 are the audit's own mistakes and 2 are small slips.
Three Drivers misreported CI. The cost attribution counts steering turns as grill turns.

## The run

| | |
| --- | --- |
| Campaign, run, date | real-direct, run 1, 2026-11-12 |
| PR prefix | `[eval 1 2026-11-12 real-direct]` |
| chantier at setup | 0.8.0, commit `27c1539b119be24049df227773add3c221657885`, with uncommitted changes |
| chantier now | the same commit |
| Sandbox base | `6e87a361c1b192e6d081c162f0cb2cc28bb72b25`; the workspace's root commit is the base |
| Batch | batch-01, mode parallel, steered by the Chief of Staff (direct), host claude |
| Models | chief-of-staff: claude-opus-5-5 (1) |
|  | coder: claude-sonnet-5-5 (9) |
|  | conflict-resolver: claude-sonnet-5-5 (5) |
|  | cr-driver: claude-sonnet-5-5 (5) |
|  | inspector: claude-sonnet-5-5 (14) |
|  | verifier: claude-sonnet-5-5 (23) |

"With uncommitted changes": the chantier checkout held three untracked files at setup
(`commands.py`, `concepts.md` and `state.py` at its root) and an untracked `.agents/`. They are not
part of the plugin's folders, and no card reads them. They were neither the run's nor touched by it.

## What was tested

The sandbox project `shelf` is a small reading list served on the web. Five frozen and specified
CRs ran in one parallel batch: delete-item, edit-item, status-filter, json-api and stats-page. It
had 3 slots and a $20 budget. There was no Foreman. The Chief of Staff steered the batch itself
(direct mode) and played the user: the go, every merge with `sandbox.py merge`, the pause, the
audit and the close. Nobody typed during the run. The session was a Claude Desktop Code session in
auto mode, with Remote Control on.

## What happened

The batch ran from about 19:41 to the last merge at 20:03 UTC, about 23 minutes. PRs merged in
the order they became ready: #1, #3, #4, #5, #2.

- **CR-103 status-filter** (PR #1) adds a `?status=` filter and a nav to the list. It needed 1
  round and was merged first.
- **CR-102 edit-item** (PR #3) needed 1 round. The Inspector's first verdict was `FIX-REQUIRED` on
  the PR body only, which did not count as a new round. The CR was ready before PR #1 merged, so it
  went back to its Driver with `take --note "rebase: CR-103 merged"`. The rebase was clean, the
  long gate and the Verifier ran again, and it was merged.
- **CR-104 json-api** (PR #4) adds `/api/items`. It needed 2 rounds; the second reverted a stray
  whitespace edit the Inspector flagged. Rebasing after CR-102 conflicted in `app.py`. A
  conflict-resolver kept both sides and an Inspector approved the resolution. It was merged.
- **CR-105 stats-page** (PR #5) needed 2 rounds; round 1 had put a UTF-8 byte-order mark in three
  files, which the Inspector caught. Rebasing after CR-104 conflicted in the README's Routes
  table, and a conflict-resolver settled it. It was merged.
- **CR-101 delete-item** (PR #2) was the costliest, at $3.32, and used all 3 rounds. It was still
  working while the others merged, and it rebased three times. The resolutions in `item.html` and
  `README.md` each needed a conflict-resolver, and one of them added a byte-order mark, which round
  3 removed. It was taken back once from `ready` (after CR-104 merged, with PR #2 conflicting) and
  merged last. The ids are kept by storing `{"next_id": N, "items": [...]}`. That touched
  `tests/test_store.py`, outside the specification's file list, and the PR body discloses it.

Nobody asked a question and no CR was blocked. The budget was never at risk, no force push was
refused, and no escalation happened.

## Findings

1. **Three Drivers wrote "no CI" while CI ran.** CR-103's, CR-105's and, at first, CR-101's
   Drivers said the repository has no CI, in their hand-backs and PR bodies. A `test` check ran
   green on every PR. It matters because a PR body that denies its CI misleads the reviewer, and
   the Verifier let the claim pass. The fix: the Driver card names `gh pr checks <n>` at the
   pushed head as the only source for a CI claim, and the Verifier checks the body's CI line.
2. **Claude Desktop's "Auto-fix pull requests" fights the batch.** Auto-fix was on in the
   session (how it came on for these PRs is not known). It sent the steering session merge-conflict events for
   PRs #2 and #5, asking for a merge commit pushed to the branch, while their Drivers were
   rebasing. The Chief of Staff ignored them, as rule 3 and the rebase flow require. A steering
   session that obeyed would have pushed onto a Driver's branch mid-rebase. The fix:
   `hosts/claude-code.md` should say that Auto-fix events on a CR's PR are the Driver's work and
   are never acted on by the steering session. It could also say how the user turns Auto-fix off
   for an eval.
3. **Cost attribution: steering turns are counted as grill turns.** No CR was grilled and no
   spec-writer ran. Yet `cost` put $1.25 on "grill and specifications with the user" during the
   run, $2.43 at the close. The steering row shrank from $1.33 to $0.99 between two readings: the
   turns were reclassified after the fact. The likely cause: the output of `take` and the Drivers'
   prompts name each CR's `03-change-spec.md`, which the attribution reads as a grill turn. This
   matters because the steering share of the scorecard reads that row, so in direct mode it is
   understated. The fix: in the steering window, do not count a path that only appears in a
   `take` output or an `Agent` prompt.
4. **The audit counts the Verifier's detached worktree as a breach (3 FAILs).** J3's rail allows
   "the Verifier's detached one". `audit.py` checks `creates no worktree` for every worker,
   Verifier included (line 494). The three Verifiers flagged each ran `git worktree add --detach
   … origin/main` for their "before" capture, as the Verifier's card says. The fix: exempt a
   Verifier's `--detach` worktree from that check.
5. **The audit's C9 check flags the report refresh (1 FAIL).** `status-layout.md` says to run
   `status --refresh` *with no epoch* before every report. In direct mode `audit.py`'s
   `DIRECT_EPOCH_COMMANDS` matches every `status --refresh` of the steering session and fails the
   ones without `--epoch`. The fix: in C9, exempt a `status --refresh` with no epoch, or require
   the epoch only on the loop's wakes.
6. **J14 "read the project's rules" (1 FAIL), a timing slip.** The Chief of Staff ran
   `$CHANTIER rules` at the start of the session, before `open`, and not again after its claim.
   The audit reads only from the claim on. The Foreman card asks for the rules at the start of
   every batch, so the steering session should run them again right after its claim.
   `chief-of-staff.md`, "Steering a batch yourself", could say so in one line.
7. **A Verifier wrote outside its folders (1 FAIL).** Verifier `ab3ea4ac68` (CR-101) wrote a probe
   script, `run3.py`, into the host's session scratchpad. That is outside both of its `writes:`
   folders. The guard sees only Write and Edit, and this was a shell or scratchpad write. It was
   harmless, but it breaks J3. The fix: the Verifier's card says its scratch scripts go under its
   `work/verifier/` folder, never the host's scratchpad.
8. **A rebase note raced a ready hand-back.** After PR #4 merged, the Chief of Staff sent CR-101's
   Driver a plain `note rebase:` just after it had handed back ready. The Driver rightly refused
   to work without a `take` and asked for one, at the cost of one exchange. The fix: the steering
   card says to read `status` for the CR's state just before sending a `note rebase:`.
9. **A CR that works while others merge pays for each merge.** CR-101 cost $3.32 of $9.22,
   through three rebases with a conflict-resolver each time. Every CR of the kit touches the
   README's Routes table, and several touch `app.py` and the templates. This is a property of the
   kit in parallel mode, worth knowing when the modes are compared, rather than a defect.
10. **Byte-order marks from PowerShell.** A Coder (CR-105, round 1) and a conflict resolution
    (CR-101's README) added UTF-8 byte-order marks. Inspectors caught both. The Coder's and
    conflict-resolver's cards could repeat rule 9's "UTF-8 without a BOM", with the PowerShell 5.1
    cause.
11. **The description pass failed three times on a missing record.** Three Verifier first passes
    gave NOT VERIFIED only because the PR body claimed an Inspector review the CR log did not
    record. Each Driver then recorded it and the second pass was VERIFIED. The fix: the Driver
    card says to record the Inspector's pass as a note before writing the body.
12. **`status` without `--refresh` shows a stale spend.** It printed $0.57 long after `cost`
    said $9.57. It could print the age of its figure.
13. **The board did not start:** `error: board not started: [WinError 10048]`. The port was
    already in use, probably by another session's board. It did not block anything, as the card
    says.

## The kit on the host

- **`setup.py`'s allow rules:** setup wrote the workspace's `.claude/settings.local.json` with
  the two merge rules (`Bash(…sandbox.py merge *)`, `PowerShell(…sandbox.py merge *)`), and
  nothing else. The five `sandbox.py merge <n>` calls ran in the PowerShell tool with no prompt
  and no refusal. They worked. But the session was in auto mode, where an allow match resolves at
  once and so would a classifier pass. This run cannot tell whether the rule or the classifier let
  them through. A session in the default mode would settle it.
- **`sandbox.py merge`:** it worked 5 times out of 5. Each time it printed `merged PR #<n> at
  <sha> into main by rebase`, and the audit's C12 confirms that every PR merged under the run's
  prefix is the batch's. It refused nothing, since every PR was open, prefixed and green, so its
  refusals were not exercised.
- **`sandbox.py reset` (plan only; `--yes` was never run):** after the run it printed `main is at
  f3cdcbd…`, `open PRs: none` and the five pushed `chantier/batch-01/*` branches. Its plan: delete
  those 5 branches, then force-push the base `6e87a36` to `main`. It reads `git ls-remote`, which
  returns the run's `refs/pull/1/head` to `refs/pull/5/head`. `parse_refs` drops every ref outside
  `refs/heads/` and `refs/tags/`, so the plan never names them and leaves them in place. GitHub
  keeps them, and no push can delete them, as the README says. After a reset, each run leaves its
  `refs/pull/<n>/head` behind, at the heads judged (00495aa, 4558b2f, 61e2fad, 5581287, dd62412).

## Direct mode: the host lines this run proved

`hosts/claude-code.md` marks these unproved for direct mode:

- **A Driver's `SendMessage` to `main`:** seen working. All five Drivers' hand-backs reached the
  Chief of Staff's conversation, as did CR-101's mid-run line asking for a `take`. The Chief of
  Staff's messages to a Driver also worked, and a message to a Driver that had ended resumed it.
- **The heartbeat in the Chief of Staff's own session:** armed with `ScheduleWakeup` (1800 s) and
  stopped with `stop: true` after `pause`. No timed wake fired: the batch finished in about 23
  minutes, inside the first interval, and hand-back notifications woke the session each time. The
  arming and the stop are seen; a wake firing is still unproved. Also, the `/loop` skill reads a
  trailing "every 30m" as a fixed cron interval, while the host card wants `ScheduleWakeup`: the
  heartbeat's prompt should not end in "every 30m".
- **The `Chief of Staff, steering the batch` cost row:** seen and priced at $0.99 (18 calls,
  10.7%) at the audit, $1.18 at the close. It is understated by finding 3.
- **A refused force push judged and run by the Chief of Staff:** not seen. Every Driver's
  `--force-with-lease` push went through, though none of the recommended allow rules was set (P10
  warned of 19 missing).
- **`order qa` refused while the batch runs:** not tried.

## Scorecard

| id | rail | mark | evidence |
| --- | --- | --- | --- |
| C1 | `take` refused with no free slot | not seen | no take was attempted with a full slot |
| C2 | `take` refused while `after` is unmet | not seen | no dependency |
| C3 | budget refusals | not seen | $9.41 of $20 |
| C4 | round limit refusal | not seen | CR-101 used 3 of 3 and needed no fourth |
| C5 | `gate` | seen, right | 11 gate events, each with its head and command |
| C6 | `verdict` bound to a clean head | not seen | no refusal |
| C7 | `handback ready` needs PR, gate and VERIFIED at the head | seen, right | 5 CRs |
| C8 | `ship` | not seen | no refusal |
| C9 | steering commands carry the epoch | seen, wrong (audit's mistake) | flagged only `status --refresh` with no epoch, which `status-layout.md` requires before a report (finding 5) |
| C10 | the heartbeat | seen, right in part | armed, then stopped right after `pause`; no wake fired before the end |
| C11 | `release go` | not seen | no release |
| C12 | only the steering session merges | seen, right | 6 checks |
| C13 | `order qa` refused while a direct batch runs | not seen | not tried |
| C14 | `pause` and `close` | seen, right | 7 checks; `close` priced the final cost |
| C15 | `open` refused while a batch is open | not seen | |
| C16 | merged CR folders | seen, right | 5 checks |
| C17 | `take` of a ready CR needs `--note` | not seen | every take of a ready CR had its note |
| C18 | a release on `order confirm` | not seen | |
| C19 | `order drop` | not seen | |
| C20 | a fix restarts the release | not seen | |
| J1 | agents' prompts | seen, right | 224 checks |
| J2 | who starts whom | seen, right | 57 checks |
| J3 | worker boundaries | seen, wrong | 4 FAILs: 3 Verifier detached worktrees, which the rail allows (finding 4); 1 Verifier write to the host's scratchpad (finding 7) |
| J4 | Driver's worktree, rebase, lease push, explicit paths | seen, right | 11 checks |
| J5 | draft, then ready on the default branch, prefix, CI green | seen, right | 5 checks |
| J6 | Driver reads CI with the forge's CLI | seen, wrong | all 5 read `gh pr checks`, but 3 reported "no CI" while it ran (finding 1) |
| J7 | Verifier at the pushed head | seen, right | VERIFIED at each merged head; the description passes caught unrecorded claims (finding 11) |
| J8 | `FIX-REQUIRED` on the body only is not a round | seen, right | CR-102's first inspection |
| J9 | question to the user | not seen | no question |
| J10 | rebase after each merge in parallel | seen, wrong | every open PR went back after each merge, and a conflicting ready PR was found with `gh pr view --json mergeable`; one note went to a Driver whose CR was ready, without a `take` first (finding 8) |
| J11 | refused force push | not seen | no refusal |
| J12 | `writes:` lines | seen, right | 51 checks |
| J13 | `git status --porcelain` before reports | seen, right | only `.agents/` untracked |
| J14 | rules, cleanup, retro, pause | seen, wrong | the rules were read before the claim, not after (finding 6); cleanup, retro and pause right |
| J15 | the host's message limit | not seen | direct mode, no send between sessions |
| J16 | report format | seen, wrong | the Completion report kept the shape; the progress updates during the run were short prose, not the Progress skeleton |
| J17 | context windows | seen, right | 56 checks; peak Driver 141k |
| J18 | a CR sent back has its PR turned to draft first | seen, right | CR-102 and CR-101's Drivers |
| J19 | escalation | not seen | |
| J20 | CR names | not read | |
| J21 | state only through `$CHANTIER` | seen, right | 57 checks |
| J22 | the steering session never codes or pushes | seen, right | 1 check |
| J23 | release drafts | not seen | |
| J24 | blocked hand-back words | not seen | no `blocked` |

**Cost:** $9.22 at the audit, $9.41 at the close (the close turns added steering). The steering
share at the audit is 10.7% (the Chief of Staff steering the batch, $0.99 of $9.22). Finding 3
says why that share is understated.

## Numbers

- **Duration:** about 23 minutes, from `open` (about 19:41 UTC) to the last merge (20:03:52
  UTC).
- **Cost at the close:** $9.41 of a $20 budget. The steering session took $1.18 (13%), the
  Drivers $3.61 (38%) and the workers $4.62 (49%).
- **Cost by CR (`cost --by cr` at the audit):**
  - CR-101 delete-item: $3.32
  - CR-105 stats-page: $1.40
  - CR-102 edit-item: $1.35
  - CR-104 json-api: $1.20
  - CR-103 status-filter: $0.96
  - steering: $0.99
- **Cost by agent (`cost` at the audit):**
  - CR Drivers: $3.61 (176 calls)
  - Verifiers: $2.50 (181 calls)
  - Inspectors: $1.04 (55 calls)
  - Coders: $0.85 (59 calls)
  - conflict resolvers: $0.24 (23 calls)
  - Orchestration (steering + Drivers): 50% of the batch's spend.
- **Cache:** 0 timed calls after the cache expired, and 0 Drivers restarted.
- **Outside the budget:** "grill and specifications" $2.43 (39 calls; misattributed, finding 3);
  the Chief of Staff's whole session $3.93 (context 244k tokens at its peak, 0 compactions).
- **Agents started:** 56. They were 5 CR Drivers, 9 Coders, 14 Inspectors, 23 Verifiers and 5
  conflict resolvers.
- **Rounds:** 1, 1, 2, 2, 3, for 9 in all.
- **Audit:** 630 of 636 checks passed.
- **Judge:** 6 pass, 0 fail, 0 not run.

| CR | PR | head judged | hidden tests | suite | result |
| --- | --- | --- | --- | --- | --- |
| CR-101 delete-item | 2 | 4558b2f | 5 passed | 67 passed | pass |
| CR-102 edit-item | 3 | 61e2fad | 5 passed | 49 passed | pass |
| CR-103 status-filter | 1 | 00495aa | 6 passed | 40 passed | pass |
| CR-104 json-api | 4 | 5581287 | 6 passed | 58 passed | pass |
| CR-105 stats-page | 5 | dd62412 | 4 passed | 60 passed | pass |
| main (5 CRs) | - | f3cdcbd | 26 passed | 88 passed | pass |

## For maintainers

chantier 0.8.0 at `27c1539b119be24049df227773add3c221657885`. The checkout had untracked files,
listed under "The run". The six failed audit checks, verbatim:

```text
- FAIL [J3] a575690943 (verifier) creates no worktree: the Driver did
- FAIL [J3] aa4b6f3168 (verifier) creates no worktree: the Driver did
- FAIL [J3] ab3ea4ac68 (verifier) edits nothing but its notes and proof: ['C:\\Users\\gaeta\\AppData\\Local\\Temp\\claude\\c5f720b1592bec19\\bd7f6b12-6a6f-436b-b052-ba60efdf5909\\scratchpad\\run3.py']
- FAIL [J3] ac57a2037e (verifier) creates no worktree: the Driver did
- FAIL [C9] every steering refresh, take, agents set, order done, cancel and pause carries its epoch: uv run --script "C:/Users/gaeta/Projets/chantier/skills/chantier/scripts/cli/cha
- FAIL [J14] the steering session read the project's rules (`chantier rules`)
```

To reproduce: `sandbox.py reset --yes`, then `setup.py real-direct <workspace>`, then the
runbook's prompt with `parallel`, in a Claude Desktop Code session on the workspace. The batch's
retro is kept in the workspace's archive (`5-archives/261112-2003-101-delete-item/retro.md`). The
sandbox is left as the run ended: 5 merged PRs, 5 branches, `main` at `f3cdcbd`.
