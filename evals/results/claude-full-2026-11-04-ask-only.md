# claude-full, 2026-11-04, Foreman sending only what needs the user

**Verdict:** passed with findings. Seven changes and a release went out and every check passed, but
the run needed the user's word in the Foreman's session once and showed messages and PRs that only
a later event could have recovered. These findings are the content of v0.3.

## What was tested

chantier ran the whole `tasks-cli` campaign: six feature CRs and a release, three at a time, with
the Foreman left linked and sending only the `ask` lines. The user approved the grant, the release
PR's merge and the tag.

## What happened

- **CR-101, CR-102, CR-105, CR-106.** Built, reviewed, green and merged, in one or two rounds.
- **CR-103, `list --json`.** Its PR was `ready` while in conflict. It took three Drivers and four
  failed merges before it went through.
- **CR-107, `stats`.** A transient classifier refusal blocked it; relaunched on the user's word, it
  asked a style question and was dropped.
- **CR-108, `--version`.** The fix the release found. Merged under the grant, by the Chief of Staff
  with `--escalated` after the Foreman was refused: the first use on a real classifier.
- **CR-104, release v0.2.0.** A first attempt found the fix, a second one shipped PR 7. The spawn
  of a Release driver was refused, the user's line in the Foreman's session lifted it, and the tag
  went out on the user's approval.

## Findings

1. **A ready PR in conflict stayed ready.** Nothing rechecked it unless a merge followed (CR-103),
   and `ask ready` did not check it either. Done in v0.3: the hand-back and each wake recheck.
2. **A classifier refused the Release driver's spawn, and `--escalated` does not cover a spawn.**
   Only a line typed in the Foreman's session lifted it. Done in v0.3: the release PR merges on a
   `merge` line with no new Driver, and the docs recommend Remote Control and that line.
3. **The Foreman's "only stop and pause" rule dismissed the user's "Oui" in its chat.** The user had
   to type a full line. Done in v0.3: the rule lets that line through, for the refused action only.
4. **An order or an ask lost on the way stayed lost.** Nothing went wrong this time, but only by
   luck. Done in v0.3: a wake runs pending orders, and `chantier asks` keeps every ask.
5. **The cost reached the user only on request.** Done in v0.3: a line per CR, a summary at the end.
6. **`spent` moves only at a heartbeat.** It read $0.17 for most of the run, then $8.00. To do: the
   budget check may be up to 55 minutes late.
7. **The limit of 10 did not refuse this time.** The Foreman sent more than 10 messages. The user
   typed in its session on the way, and some messages were queued rather than delivered. Not
   explained further: keep relying on `chantier asks`, not on the absence of a refusal.
8. **Minor.** CR-102's Driver skipped `gate --long` after a rebase. CR-105's review left minor
   findings, a BOM among them. The Foreman miscounted its messages and sent `ask ready CR-103`
   twice. The release's `hand-back ready tag v0.2.0` recorded `tag` as the release. Each new
   workspace must be trusted once in the app.

## Numbers

- **Duration:** 62 minutes, from opening the batch to its landing.
- **Cost:** $8.41 in all.
  - By role: Foreman $2.97, Drivers $1.87, verifiers $0.75, coders $0.72, conflict resolvers $0.52,
    Inspectors $0.42, Release drivers $0.42, docs reviewers $0.35.
  - By change: CR-105 $1.20, CR-103 $1.08, CR-106 $0.73, CR-102 $0.69, CR-108 $0.52, CR-101 $0.48,
    CR-104 $0.42, CR-107 $0.31 (the Foreman's $2.97 apart).
- **Audit:** 531 of 531 checks passed.

## For maintainers

- chantier 0.1.0, `main` at 4557159. Foreman and every other agent on Sonnet 5.5, operator on
  Opus 5.5; Windows 11, Claude Desktop.
- 17 orders were sent. The report's $8.36 stops at `land`; `cost` counts the Foreman's last turn.
