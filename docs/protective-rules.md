# Protective rules

The rules of chantier's cards, CLI and hook that protect the user or the repository, with where each
one lives. It replaces the old cards' inventory, removed by this change. A change that deletes or
rewords a home updates its line in the same pull request.

States: `held` (a floor line, a card, a refusal or the hook holds it), `restored here` (added by the
change that made this file), `to add` (needs code that does not exist yet). A card path is relative to
`skills/chantier/references/`; a refusal quotes a span of its message.

A plan step is a step of section 6 of the cleanup plan, in the planning surface:
`projects/chantier/changes/2-backlog/P1/card-inventory-open-rows/work/fable-review-plan.md`.

Ids: `P<n>` is row n of the plan's section 5; `A`, `B`, `C` and `D` number the statements of section D
of the review's verdicts, by slice, in their order; `N` numbers a rule that the last reading of the old
inventory added. A line that states one rule listed twice carries every id (`P1/D1`).

## 1. Merging and the words about a merge

| id | rule | state | home |
|---|---|---|---|
| P1/D1 | Never merge without the user's word; "you can merge it" only after the ready line, never on a green CI or a draft. | `held` | floor 1 "Never merge without the user's word."; `topics/merge-words-p2.md` "only after the `ready-to-merge` line (or `stack-ready-to-merge`) has reached you"; `topics/merge-words-p2.md` "never on a Driver's progress, a green CI or the forge's look"; `topics/merge-words-p1.md` "A draft is named with "do not merge" and what blocks it" |
| B1 | Check that the forge shows the PR merged into the default branch before `order merged`; unconfirmed records nothing. | `held` | `topics/wakes-forge.md` "A merge the forge does not show: record nothing"; `foreman.md` "`order merged` only for a merge the forge shows"; `topics/watcher-events-p1.md` "merged into the default branch, or for `landed with` its base's PR merged there" |
| D2 | A draft on another CR's branch is never called ready. | `held` | `topics/merge-words-p1.md` "a draft on another CR's branch is never "ready"" |

## 2. Rebase and push

| id | rule | state | home |
|---|---|---|---|
| P2 | Rebase only, with `--force-with-lease`, only the CR's own `chantier/*` branch, never the default branch, a yes included. | `held` | floor 2 "Rebase only, with `--force-with-lease`, and only on the CR's own branch."; refusal of `push` "push only pushes a CR's recorded"; `chief-of-staff.md` "the default branch and any force push of it never, a yes included"; `foreman.md` "no other branch even on a yes" |
| B9 | A steering rebase only after the branch check; a conflict stays stopped, no `--abort`, no resolution. | `held` | `topics/refused-rebase-run.md` "leave the rebase stopped (no `--abort`, no resolution)"; `topics/refused-rebase.md` "You resolve nothing."; `topics/refused-rebase.md` "the check is a hard refusal: the branch is covered" |
| N2 | A stack's rebases start from a read of the stack; a resumed one goes on where it stopped and redoes none. | `held` | `topics/stack-restack.md` "Run `$CHANTIER stack` before a take's first rebase"; `topics/stack-record.md` "A resumed take goes on from the first CR, bottom up, whose last `restack: on …` note does not name the current heads or has no later `judged` note." |
| N3 | A Driver rewrites only its scope: its own CR's branch; the stack's, only the branches of CRs with no live Driver. | `held` | floor 2 "Rebase only, with `--force-with-lease`, and only on the CR's own branch."; `concepts.md` "the rebase and the push the Driver may run, and their scope"; `stack-driver.md` "You own the branches of the CRs with no live Driver"; `stack-driver.md` "A `working` CR's branch is its Driver's." |
| A14 | No forge branch protection is read; a push refused as protected is never retried. | `held` | `foreman.md` "no failed or protected push retried, no branch protection read"; `topics/refused-push-steering.md` "and never retry it"; `topics/refused-push.md` "After a refusal never retry it and never run a raw `git push`." |
| A15/D13 | A steering push only for `chantier/*`: a refused push of any other branch, the default one included, is never pushed, a yes included. | `held` | `foreman.md` "no other branch even on a yes"; `chief-of-staff.md` "never the default or a protected branch"; `topics/refused-push-steering.md` "push nothing, ever; a user's yes does not push it"; `topics/refused-push-chief-p1.md` "push nothing, ever" |
| P2-code | For a refused push or rebase the CLI checks the branch and prints the exact command, and the agent runs it, so the host still checks it (card-cleanup-Q2). | `to add` | plan step 15, steering `push` and `rebase`. Today the rule is held by the lines above. |

## 3. Never discard work

| id | rule | state | home |
|---|---|---|---|
| P3/A12 | Never discard work: no `stash`, `reset --hard` or `add -A`; the main checkout is never cleaned by force, after a wrong-place git command included. | `held` | floor 5 "Never discard the worktree's work."; `cr-driver.md` "run `git stash`, `git add -A`, `git add .`, a merge commit, a rebase with `--rebase-merges`, `--exec` or `-x`, `git reset --hard` or anything that discards the worktree's work"; `topics/trouble-git.md` "never cleaned by force."; `stack-driver.md` "`git reset --hard`, or retarget a PR by hand" |
| A3 | A release's new attempt starts in a new worktree, never `reset --hard` of the old one. | `held` | `release-driver.md` "in a new worktree: never `git reset --hard` an old one"; `topics/release-ship.md` "never a `reset --hard` of the old one" |
| B2 | The main-checkout fast-forward is only `merge --ff-only --no-overwrite-ignore`; untracked files are never touched. | `held` | `foreman.md` "`--no-overwrite-ignore` fast-forward of a clean main checkout"; `topics/main-checkout-p2.md` "never pull, reset, rebase, stash, clean, checkout, switch, nor a merge without both flags"; `topics/main-checkout-p2.md` "Untracked files are never listed, read, moved or deleted" |
| A13/B13 | A dropped CR's PR is closed with no `--delete-branch` and no comment; a CR moved to the backlog is drafted only; the Foreman never removes a trashed, backlog or `3-ready` CR's worktree or branch. | `held` | `foreman.md` "closing/drafting a dropped CR's PR per its drop order (no comment, branch kept)"; `topics/stack-changes.md` "no `--delete-branch`, no comment"; `foreman.md` "remove a trashed, backlog or `3-ready` CR's worktree"; `topics/drop.md` "no `--delete-branch`, no comment"; `topics/stack-changes.md` "its PR to a draft, no close, no comment" |
| B18 | Never `rm -rf` or `Remove-Item -Recurse` on `.claude` or on temporary folders named by a wildcard. | `held` | `topics/host-refused.md` "`Remove-Item -Recurse -Force` or `rm -rf` on `.claude`, or on temporary folders named by a" |
| D24 | Before proposing to move a session off a worktree, check that nothing is left behind. | `held` | `topics/session-start.md` "check nothing is left behind" |
| P3-code | A hook refuses `stash`, `reset --hard` and `add -A` in a Driver's shell. | `to add` | no step of plan section 6 brings it (the plan's table: a hook deny list was filed apart). Today the rule is held by the lines above. |

## 4. Where an agent may write

| id | rule | state | home |
|---|---|---|---|
| P4/A11 | A Driver and its workers write only where `writes:` says, nothing in the repository's git folder, nothing in the main checkout. | `held` | hook `hooks/register.tsx` (Claude Code only) "is outside the folders this agent may write in"; `cr-driver.md` "the main checkout is read-only for you"; `topics/trouble-git.md` "A Driver and its workers write nothing in the repository's git folder" |
| N4 | A worker's prompt is `brief`'s output passed unchanged: one with no `writes:` line is not guarded. | `held` | `concepts.md` "passes the output unchanged"; `concepts.md` "a prompt without the line is not guarded" |
| N5 | A review step added by the project writes, commits, pushes and stashes nothing. | `held` | `review-step.md` "Never write a file, commit, push, rebase, merge, `git stash`" |
| A19 | Never use the live `$CHANTIER` line on a scratch project; `git init` it first. | `held` | `verifier.md` "at the live planning folder, or the prompt's `$CHANTIER` at the scratch project"; `topics/verifier-scratch.md` "Never use the prompt's `$CHANTIER` line as printed: it names the live project."; `topics/verifier-scratch.md` "run `git init <scratch project>` before anything else there" |
| A20 | A too-long Windows path is a stop: no shorter folder outside `writes:`. | `held` | `topics/verifier-scratch.md` "no shorter folder outside your `writes:` folders"; hook `hooks/register.tsx` (Claude Code only) "is outside the folders this agent may write in"; `topics/verifier-scratch.md` "failing on its length) is a stop" |
| C17 | A project's clone on a surface is touched only by `git -C <clone>`; a missing clone is cloned only on the user's word. | `held` | `topics/grill-surface.md` "Never touch the project's clone but by `git -C <clone>`."; `topics/grill-surface.md` "is cloned on the user's word" |
| C21 | A demo fixture stays outside the tracked files and is removed at the end; the Chief of Staff's subagent never commits, pushes or writes in a CR worktree. | `held` | `topics/demo-p1.md` "It never starts an implementation: no commit, push, PR, or write in a CR's worktree."; `topics/demo-p2.md` "Prepare any fixture outside the repository's tracked files and remove it at the end."; `chief-of-staff.md` "let a subagent implement" |

## 5. An irreversible release action

| id | rule | state | home |
|---|---|---|---|
| P5/A5/D5/D6 | An irreversible release action waits for the user; `publication done:` only from the user's quoted words, never guessed; "auto" covers one release only, never the announcement, a fix, `order confirm` or a budget raise; the main-checkout step (the tag) is never the release driver's. | `held` | floor 6 "An irreversible release action waits for the user."; refusal of `release go` "every irreversible step waits for their merge"; `chief-of-staff.md` "record "auto" and `publication done:` only from the user's own words, quoted"; `release-driver.md` "run a step of the procedure that runs in the main checkout"; `topics/release-merged.md` "is never yours, in the main checkout or your worktree"; `topics/release-chief-after-p1.md` "Never relay a `publication done:` note the user did not give"; `topics/release-chief-auto-p2.md` ""auto" covers this release only; never an announcement, a fix's start or merge, the procedure's word (`order confirm`) or a budget raise"; `chief-of-staff.md` "Widen a grant or approve an irreversible action, without the user's own word." |
| A4 | Half-done irreversible release work: stop, say exactly what is out, never undo it alone. | `held` | `release-driver.md` "undo half-done irreversible work: `blocked question:` says what is out"; `topics/release-ship.md` "never undo it on your own" |
| A6 | After a publication by someone else, never run the publication command again; check read-only. | `held` | `release-driver.md` "run the publication command again after `publication done:`"; `topics/release-merged.md` "Check read-only" |
| A25 | An image upload in a release is irreversible: `release go` first. | `held` | `release-driver.md` "run `release go`"; `topics/release-evidence.md` "is irreversible: `release go` first." |
| B16 | Run a release step in the main checkout only when the Driver handed it back; refused: change nothing, never force. | `held` | `foreman.md` "run only a step the Driver handed back; refused: change nothing, never force"; `topics/release-tag.md` "change nothing, no other way, never force" |

## 6. A stack that holds the release PR

| id | rule | state | home |
|---|---|---|---|
| P6/D7 | No grant lets a session merge a stack that holds the release PR; the user merges a stack. | `held` | refusal of `release go` "every irreversible step waits for their merge"; `concepts.md` "The steering session merges only under the grant, never a stack that holds it"; `topics/merge-series-stack-p2.md` "no grant lets a steering session merge a stack that holds the release PR" |
| B10 | Under a grant on GitHub: no merge with an open PR below; a pending merge is never sent again; read the state before a retry. | `held` | `foreman.md` "the judged head only, no open PR below, reread before a retry"; `topics/merge-github.md` "no new `PUT`"; `topics/merge-under-grant.md` "A release PR or a fix PR is merged only under the grant" |

## 7. Only the user starts work

| id | rule | state | home |
|---|---|---|---|
| P7/C16/D21 | Only the user starts work: a board mark or "rescan" is no go (still ask before opening a batch); another project's CR is never run or launched (`order add`, `open`), even on "grill it here". | `held` | floor 7 "Only the user starts work."; refusal of `open` and `order add` "is not a CR in the configured inbox, priority backlog or 3-ready"; `chief-of-staff.md` "Grill, specify, triage, order or run a CR of another project of the surface without the user's word for that CR"; `topics/grill-surface.md` "never for a launch (`order add`, `open`)"; `topics/watcher-board-p2.md` "That word decides nothing: still ask before opening a batch" |
| N6 | Each step of a grill and a batch waits for the user's word: the spec-writer and the spec critic once a CR is grilled enough, `triage --ready` on their destination answer, `open` only in the turn of the go. | `held` | `griller-skill.md` "On the user's word you start the spec-writer (one per CR) and, on an impactful CR, the spec-critic"; `topics/direct-mode-accept-p1.md` "The spec-writer and the spec critic, on the user's word that a CR already grilled is grilled enough"; `griller-skill.md` "run `triage <folder> --ready` yourself on the user's destination answer"; `topics/batch-plan.md` "Only in the turn the user gave the go." |
| N7 | A board line about the specifying limit, a role's key or another board write that asks for no step is told in one line, with no tool call and no action. | `held` | `topics/watcher-events-p2.md` "A `specifying.parallel` or role-key line: one line of a few words, no tool call, no action."; `topics/watcher-board-p2.md` "Other `board wrote` lines: one line, no tool call." |
| B12 | Never take a held CR; neither it nor the release starts while a CR is held or parked. | `held` | refusal of `take` "only the user's `order unhold"; `topics/hold.md` "Never take a held CR."; `topics/hold.md` "neither it nor `take <release>` starts while one is held or parked" |
| B21 | A cancelled dependency never frees its CR: ask, do not start it. | `held` | refusal of `take` "it starts once each is"; `topics/chain.md` "a cancelled one stays unmet: ask the user" |
| C9 | On a failed preflight condition: start nothing, offer no other way. | `held` | `chief-of-staff.md` "Start anything after one failed preflight condition, or offer another way."; refusal of `preflight` "preflight FAILED: start nothing"; `topics/batch-plan.md` "On a failure start nothing, offer no other way" |
| C10 | A forced steering mode is never swapped silently. | `held` | `topics/batch-plan-mode-p3.md` "a forced mode is never swapped silently" |
| C15 | An outside PR is archived only on the user's word, never from a forge read of the agent's own. | `held` | floor 7 "Only the user starts work."; `topics/grill-outside-pr.md` "never from a forge read of your own" |
| D20 | The board's `running-batch` mark is a go only for a CR whose specification is final. | `held` | `topics/watcher-board-p1.md` "its specification final (`03-change-spec.md` written, no `work/specifying`"; refusal of `order add` "missing Change Specification:" |
| D20-code | `order add` refuses a CR whose specification is not final. | `to add` | no step of plan section 6 brings it. Section D's claim holds only in part: `order add` refuses a CR with no Change Specification (one in `3-ready` with its request excepted), not one whose specification is not final. |

## 8. Images

| id | rule | state | home |
|---|---|---|---|
| P8/A16/D3 | No image shows the username or the home folder; a leak found after an upload is replaced and the user told the old attachment may stay reachable, with nothing about it in the public PR. | `held` | floor 8 "No image shows the username or the home folder."; `topics/pr-images.md` "replace the image in the description with a clean capture"; `topics/pr-images.md` "a removed attachment can stay reachable, so the user is told"; `topics/pr-images.md` "Nothing about the leak goes in the public PR."; `topics/merge-gaps-p2.md` "that the old attachment may stay reachable on the forge" |
| A17 | The user's own screenshot that fails the look is not uploaded or copied. | `held` | `topics/pr-images.md` "do not upload or copy it" |
| A18 | A Driver never opens an image file. | `held` | `topics/pr-extras.md` "A Driver never opens an image file" |
| D4 | A screenshot asked of the user uses made-up paths, no username or home folder. | `held` | `topics/merge-gaps-p2.md` "with made-up paths, no username or home folder" |

## 9. Refusals

| id | rule | state | home |
|---|---|---|---|
| P9 | A refusal is reported with its exact text, never worked around, never retried another way, never by changing the permission settings. | `held` | floor 9 "Report a refusal with its exact text; never work around it."; `topics/refused-forge-chain.md` "never another form of the command, never a change to the permission settings"; `topics/refused-push-chief-more-p2.md` "or a change to the permission settings" |
| A7 | Never rerun a creating forge command after a network error without checking whether it took effect. | `held` | `topics/trouble-remote.md` "check whether the first attempt took effect" |
| A8 | A forge refusal (4xx, protected branch, failed lease) is never retried as an infrastructure failure. | `held` | `topics/trouble-remote.md` "is no infrastructure failure"; `foreman.md` "no failed or protected push retried" |
| A9 | Never read a verdict, a pass or a choice into a reply out of format, never fix it. | `held` | `topics/trouble-worker.md` "never read a verdict, a pass or a choice into it, never fix it" |
| A10 | A second refused start of a worker is never retried without its model. | `held` | floor 3 "No fallback."; `concepts.md` "never retried without the model or with another" |
| D11 | A failed post is never retried another way; if an artifact fails, the comment is not posted. | `held` | floor 9 "Report a refusal with its exact text; never work around it."; `topics/ticket-summary-post-p1.md` "if an artifact fails, the comment is not posted" |
| D14 | A refused push or rebase: once, unchanged, never `--force`, never another form, never a change to the permission settings. | `held` | `topics/refused-forge-chain.md` "Never a `--force`, never another form of the command, never a change to the permission settings."; `chief-of-staff.md` "A failed lease is told at once, never retried."; `topics/refused-push-chief-more-p2.md` "On the yes: run it once, unchanged"; `topics/refused-rebase-chief.md` "on the yes run it once, unchanged" |
| D22 | A trial refusal is said at once with its exact text; a pass proves nothing for a Driver. | `held` | `topics/trials-p2.md` "said at once with the command and the host's exact text"; `topics/trials-p2.md` "a pass proves nothing for a Driver"; floor 9 "Report a refusal with its exact text; never work around it." |
| N8 | A refusal is recorded once, whoever sees it, before the next step. | `held` | `topics/refused-push-run.md` "Record each refusal once, whoever sees it, before the next step's line." |

## 10. Processes, the board and the watcher

| id | rule | state | home |
|---|---|---|---|
| P10 | Never stop a process by name, pattern or PID; the board and watcher start and stop on the user's yes. | `held` | floor 10 "Never stop a process by name or pattern; use `close --yes` only on the user's yes."; `chief-of-staff.md` "never by name, pattern or PID (floor 10)"; `chief-of-staff.md` "started on the session's yes"; `chief-of-staff.md` "your own board or watcher too" |
| B19 | Stop a sync holder only if it is this session's own board or watcher, on the user's yes, never by PID. | `held` | floor 10 "Never stop a process by name or pattern; use `close --yes` only on the user's yes."; `chief-of-staff.md` "never by name, pattern or PID (floor 10)"; `sync-checkout.md` "never stop or kill a process"; `topics/sync-offer-p2.md` "by the host's stop of their background shell (never by a"; `skills/chantier/SKILL.md` "Never stop or kill a process for a sync, nor ask anyone to"; `skills/chief-of-staff/SKILL.md` "Never stop or kill a process for a sync, nor ask anyone to"; `skills/griller/SKILL.md` "Never stop or kill a process for a sync, nor ask anyone to"; host row `name-env-holders` "never `Stop-Process`, `taskkill` or `kill` on a holder" (`hosts/claude-code.json`; `hosts/copilot.json` "never a stop or a kill of a holder") |
| C22 | The board is stopped only by `serve --restart`, one yes per restart; a refused restart's stop command is printed, never run. | `held` | floor 10 "Never stop a process by name or pattern; use `close --yes` only on the user's yes."; `topics/board-restart.md` "never run by you"; `chief-of-staff.md` "a board another session serves is the user's to stop"; `topics/board-lines.md` "Never stop it yourself except by the restart"; `topics/board-restart.md` "a yes covers one restart" |
| D17 | The watcher and the board start only on the session's one yes; never stop another session's watcher. | `held` | `chief-of-staff.md` "started on the session's yes"; `topics/watcher.md` "stop another session's, or start one after the user's no" |
| N9 | The board's link and network lines are passed on to the user once; reach over the local network is said untested. | `held` | `topics/board-lines.md` "Pass each on once, in one line, as printed"; `topics/board-lines.md` "say LAN reach is untested"; `chief-of-staff.md` "or as fact what the host marks unproved" |

## 11. The host's settings file

| id | rule | state | home |
|---|---|---|---|
| P11 | The user writes the allow rules, from a command the CLI builds for the running system and host; the CLI checks they are in place; no agent writes the settings; each host has its own case (card-cleanup-Q3). | `to add` | plan step 20, `preflight --add-rules`, read in the light of card-cleanup-Q3. Today the Chief of Staff still writes them; what protects the user (only the P10 rules, only added, only on the user's yes) is held by `AGENTS.md` "on the user's yes, the Chief of Staff adds to `~/.claude/settings.json` the allow rules preflight's P10 named, and nothing else there" and `chief-of-staff.md` "Editing `~/.claude/settings.json`: only the P10 allow rules preflight named, merged, nothing else there" (under "Asks first, each only on the user's yes in this turn") |
| B17/C1 | Chantier never removes or edits an allow rule of the user's (a broad or stale one included), never arms or disarms the PR monitor, and has no `gh api` allow rule. | `held` | `topics/host-allow-broad.md` "removes or edits a rule of the user's"; `topics/host-allow-broad.md` "There is no `gh api` rule"; `topics/host-auto-fix.md` "Chantier never arms, disarms or unbinds the PR monitor"; `topics/allow-rules-more-p1.md` "never remove or edit it" |
| C2 | Nothing but `permissions.allow` of the user's settings file is written. | `held` | `topics/allow-rules.md` "Nothing else is written in any settings file"; `chief-of-staff.md` "only the P10 allow rules preflight named, merged, nothing else there" |

## 12. Tracker comments and public issues

| id | rule | state | home |
|---|---|---|---|
| P12/D10 | A tracker comment or a public issue holds no CR number, batch, role, cost or private path (a tracker comment no slug either); posted only on a recorded yes, a tracker comment for that ticket and by the Chief of Staff only. | `held` | `chief-of-staff.md` "Post on a tracker issue a text, plan or demo the user did not approve for that ticket, or one naming a CR, batch, role or cost"; `topics/ticket-summary-p2.md` "No yes, nothing posted"; `topics/retro-route-chantier-p1.md` "ask a yes per issue"; `chief-of-staff.md` "or one naming a CR, batch, role or cost, or let another session"; `topics/ticket-summary-p1.md` "no CR number or slug, batch, round, role, cost, requirement ID or `.agents/changes/` path"; `topics/retro-route-chantier-p1.md` "no project name, private path, code or text of the target project" |
| D9 | A public chantier issue holds no project name, private path, code, CR number, batch id or person's data. | `held` | `topics/retro-route-chantier-p1.md` "no project name, private path, code or text of the target project, CR number, slug, batch id, or person's name or data" |
| D12 | No agent closes or reopens an issue by hand; only the PR's closing line does. | `held` | `chief-of-staff.md` "close or reopen an issue by hand"; `topics/ticket-summary-post-p2.md` "No agent closes or reopens an issue by hand" |
| P12-code | A pattern check in the posting step. | `to add` | no step of plan section 6 brings it. Today the rule is held by the lines above. |

## 13. Never a second Driver on one CR

| id | rule | state | home |
|---|---|---|---|
| P13/B5/C5 | Never a second Driver on one CR: silence is never a reason (restart only after a proof of death or its final report); stopping a session does not prove its Agent children ended, so after a mode switch every old Driver is checked ended. | `held` | refusal of `take` "is held: lease"; `foreman.md` "never on silence alone"; `topics/direct-mode-switch-p2.md` "Never assume that stopping a session ended its Agent children."; `topics/host-driver-silence.md` "after a proof of death or the first one's final report: never on silence"; `topics/direct-mode-switch-p2.md` "Restart only the CRs (and the stack driver, QA orders) whose old Driver is shown ended" |
| B6 | Never record a hand-back for a Driver. | `held` | `topics/lost-silent.md` "Never record a hand-back yourself."; refusal of `handback` "needs --lease <n>". Note: the refusal covers the hand-back of a working CR; a CR already `blocked` hands back with no lease check |
| B7 | A Driver stopped and not restarted at once: record `stopped:` and clear its id in the same turn. | `held` | `topics/lost-outside.md` "clear the id in the same turn: `agents set <cr> - --epoch <n>` (or `stack`, `<O-k>`), after `note <cr> "stopped: <why>"` for a CR" |
| B8 | A Driver stopped from outside is restarted with no ask, whatever the host says. | `held` | `topics/lost-outside.md` "no ask, no wait for the user, whatever the host's words" |
| N10 | A stop the steering session made itself, the user's stop or hold included, keeps its own path: only a stop from outside restarts with no ask. | `held` | `topics/lost-outside.md` "Only a stop the steering session did not make."; `topics/lost-outside.md` "Its own stops (a switch of mode, a drop, the user's stop or hold, the `stop` after 3 idle hours) keep their own paths" |
| C6 | After a switch back, every Driver the Chief of Staff owns is stopped before the Foreman claims. | `held` | `topics/direct-mode-back.md` "No Driver of yours runs once the Foreman claims" |
| C7 | A Foreman session is stopped by the user, or by the Chief of Staff on the yes and only by the host's named means. | `held` | `chief-of-staff.md` "Stopping a Foreman or a process you did not start"; `topics/direct-mode-switch-p2.md` "its session is stopped by the user, or by you on the user's yes where the host row names the means" |
| P13-restart | `restart` refuses on a live lease. | `to add` | plan step 16, `restart`. Today `take` refuses a live lease. |
| P13-seat | `foreman set` refuses on a live lease. | `to add` | no step of plan section 6 brings it. Today the rule is held by the lines above. |

## 14. A CR found merged, or with a PR already

| id | rule | state | home |
|---|---|---|---|
| P14/A1/A2 | A CR found merged at hand-back: push, edit, retarget and turn nothing; a CR that shows a `PR:` link at first take: never a second PR, never a new branch. | `held` | `topics/retake.md` "never a second PR"; `topics/handback-refused.md` "Push nothing, edit nothing, retarget nothing, turn nothing ready or draft."; refusal of `handback` "no Driver to hand it back"; `topics/retake.md` "never a new branch" |
| P14-code | `push` and `ship` refuse a merged CR, and `ship` a second PR link. | `to add` | no step of plan section 6 brings it. Today neither command checks either; the rule is held by the lines above. |

## 15. Gates and waivers

| id | rule | state | home |
|---|---|---|---|
| P15/C8 | A long-gate waiver is recorded with the user's own words and a follow-up CR filed first, never as a note in a brief. | `held` | refusal of `order waive` "--follow-up <backlog folder>"; `topics/long-gate-waiver.md` "A waiver is the user's word, recorded by the Chief of Staff"; `topics/batch-plan-show-p2.md` "never a note in a brief" |
| A21 | `--no-gate` replaces only the long-gate check, and quotes the rule. | `held` | refusal of `handback` "that declares no long gate or exempts this CR"; `topics/cr-handback.md` "replaces the long gate check only, never the head, clean, pushed and verdict checks"; `foreman.md` "a `no long gate` or waiver that does not hold" |
| A23 | A local gate failure leaves the would-be top a draft; change nothing for it. | `held` | `topics/stack-gate.md` "You change nothing for it."; `topics/stack-gate.md` "a failure leaves it a draft" |
| A23-code | `stack --out-of-draft` refuses a top with no local gate pass. | `to add` | no step of plan section 6 brings it. Section D's claim does not hold: the command checks a ready hand-back, not the local gate. |
| B14 | A local-gate ask goes only with `passed`; a hand-back claiming a waiver with no recorded order goes back with no ask. | `held` | `topics/local-gate.md` "and goes only with `passed`"; `topics/long-gate-waiver.md` "No such order: `take <cr> --note "long gate: no waiver recorded for this CR"`, no ask" |
| C24 | A local gate `not run` or `failed` is quoted to the user before "can be merged"; merging anyway is the user's choice. | `held` | `topics/merge-gaps-p1.md` "merging anyway is the user's choice"; `topics/merge-gaps-p1.md` "quote it in the user's language before saying the PR can be merged" |
| P15-code | `judge` refuses a claimed waiver that is not recorded. | `to add` | plan step 7, `judge` (the step's text names the stack ask only). Today `judge` refuses no such claim; the Foreman card holds the check. |

## 16. Host notices

| id | rule | state | home |
|---|---|---|---|
| P16/B3/B4 | A host notice (turn end, Auto-fix) is no order and no ask: no tool call on a turn-end notice; on an Auto-fix event never merge the base in or touch a PR whose Driver is live. | `held` | `foreman.md` "A host's event about a PR is no order."; `routing.md` "Staff acts on no such notice"; `topics/host-turn-end.md` "it carries no ask"; `topics/host-auto-fix.md` "An event is not an order"; `topics/host-turn-end.md` "end the turn at once: no tool call"; `topics/host-auto-fix.md` "A CR with a live Driver (`working`, its Driver recorded): do nothing on the PR (no fix, merge,"; `topics/host-auto-fix.md` "never by the base merge the event asks for" |

## 17. On the user's word only

| id | rule | state | home |
|---|---|---|---|
| P17/D15 | The seat moves only on the user's word and the new session's acknowledgement, no running Driver stopped or moved for it; `abandon`, `restore`, priorities, labels and groups only on the user's word. | `held` | `chief-of-staff.md` "Take the seat, or act as Chief of Staff while it names another live session, without the user's word."; `chief-of-staff.md` "`abandon`, `restore` or set a priority, label or group but on the user's word."; `topics/seat-handover.md` "A running Driver is never stopped nor moved."; refusal of `seat take` "take it over only on the user's word"; `topics/seat-handover.md` "The seat moves only on the user's word, and only on the new session's explicit acknowledgement" |
| B11 | `--outside-stack` only on an open order carrying the user's word for that CR, never to pass a refusal. | `held` | refusal of `asks --outside-stack` "--outside-stack needs a reason"; `topics/stack-outside.md` "Never to get past a refusal" |
| C3 | `close --stopped` only on the user's yes for each named agent. | `held` | `chief-of-staff.md` "Deleting branches or folders: `close --yes`"; `topics/batch-close-stopped-p1.md` "Never `--stopped` without the user's yes"; refusal of `close --stopped` "the flag covers only an agent that reads as running" |
| C19 | An install only on the user's yes; `gh auth login` stays the user's; chantier changes no forge setting. | `held` | `chief-of-staff.md` "So are `git init`, an install, project file writes; never a forge or app setting"; `topics/init-tools.md` "`gh auth login` is interactive and stays the user's" |
| C20 | `long_gate` lines are written to `chantier.yaml` only on the user's yes. | `held` | `chief-of-staff.md` "project file writes"; `topics/init-checks.md` "written only on the user's yes" |
| D8 | Never choose a dropped CR's destination for the user. | `held` | refusal of `order drop` "ask the user when they have not said it"; `topics/order-drop.md` "Never choose for the user" |
| D16 | Two live Chiefs of Staff: do no Chief of Staff work until the user chooses. | `held` | `chief-of-staff.md` "act as Chief of Staff while it names another live session"; `topics/seat-p2.md` "do no Chief of Staff work until the user chooses" |
| D16-code | A command refuses a session whose seat another live session holds. | `to add` | no step of plan section 6 brings it. Today only `seat take` and `seat leave` refuse. |
| D18 | The board is exposed on the network only on the user's word. | `held` | `topics/remote-login.md` "on the user's word, `board.host: network`" |
| D19 | `cancel` only after a drop the user ordered, never to stop a CR that goes on. | `held` | `chief-of-staff.md` "`cancel` follows only a drop the user ordered"; `topics/recovery.md` "never use it to stop the processes of a CR that goes on" |
| D23 | A `chantier.yaml` long-gate entry is written in the main checkout only on the user's yes. | `held` | `chief-of-staff.md` "project file writes"; `topics/project-rules-p2.md` "written on the user's yes in the code repository's root `chantier.yaml`" |
| D25 | A rounds exception only for a red the batch caused, one per cause, never above `max_rounds` + 2; every other grant is the user's. | `held` | `topics/rounds-exception.md` "never above `max_rounds` + 2"; `topics/rounds-exception.md` "Every other grant of rounds stays the user's." |
| N1 | A workaround the user allows for one batch's Foreman in a worktree is passed in their words, stays in that batch and never becomes a rule. | `held` | `topics/foreman-start-more.md` "pass their words as they wrote them and never turn them into a rule"; `topics/host-foreman-worktree.md` "never becomes a rule" |

## 18. The planning surface

| id | rule | state | home |
|---|---|---|---|
| P18 | The planning surface is committed and pushed only by its writer. | `held` | `chief-of-staff.md` "Commit, pull, push or force-push the planning surface: its writer does."; `griller-skill.md` "commit, pull and push nothing"; refusal of `a write command` "the surface's writer is not running: nothing written" |
| C18 | A Griller in a surface worktree commits nothing, opens no PR and runs no `triage` or `summary` command. | `held` | `griller-skill.md` "run no `triage`"; `topics/griller-worktree.md` "commit nothing, open no PR or MR, run no `triage` and no `summary` command there" |

## 19. The grill

| id | rule | state | home |
|---|---|---|---|
| P19/C11/C12 | Record each grill answer or decision at once, with the date and the user's words; never decide "grilled enough" alone: ask only after a full restatement. | `held` | `griller-skill.md` "Record each answer in `02-answers.md` at once"; `griller-skill.md` "Restate in full before "grilled enough?"."; `griller.md` "each answer recorded in `02-answers.md` at once"; `topics/grill-restate.md` "Never decide alone that a CR is grilled enough."; `topics/grill-backlog-p1.md` "Record at once, with date and words" |
| C14 | A critic finding that touches behaviour, scope or risk is a question to the user. | `held` | `topics/grill-critic-steps.md` "a finding that touches behaviour (scope, behaviour, risk) is a question" |

## Statements no row of the plan's table groups

| id | rule | state | home |
|---|---|---|---|
| A22 | Never skip a proof pass to save budget. | `held` | `topics/handback-other.md` "Never skip a proof pass to save budget" |
| A24 | Never stop another CR's gate, nor your own because it is slow. | `held` | `cr-driver.md` "run `gate <cr> --stop` on another CR's gate"; `topics/trouble-gate.md` "Never because it is slow" |
| A24-code | `gate <cr> --stop` refuses a caller that does not drive that CR. | `to add` | no step of plan section 6 brings it. Section D's claim does not hold: the command stops the named CR's gate for any caller. |
| B15 | `gate --first` only for the critical path or the user's next merge, never at a Driver's request. | `held` | `foreman.md` "`gate --first`: a critical-path CR or the user's next merge only, not on a Driver's say."; `topics/long-gate.md` "nor at a Driver's request alone"; refusal of `gate --first` "a Driver never moves its own gate" |
| B20 | Never chain a started CR; a shared file alone is no reason. | `held` | `topics/chain.md` "A shared file alone is no reason, and a CR that has started is never chained."; refusal of `order after` ", not queued" |
| B22 | The retro critic's verdicts are followed as given; its brief carries evidence, never an argument. | `held` | `retro-critic.md` "Judge the evidence, not an author's argument or preference."; `topics/retro-critic-write.md` "Follow the verdicts as given"; `topics/retro-critic.md` "never your argument, ranking or preference" |
| C4 | `asks --read all` is never used to clear the list. | `held` | `topics/asks.md` "never to clear the list" |
| C13 | The spec critic never edits the specification and runs once. | `held` | `topics/grill-critic.md` "runs once per specification, never in a loop"; `spec-critic.md` "Never: edit the specification" |
| C23 | No delivery time without its floor; none when the gate's time is unknown; no gate run to measure it. | `held` | `chief-of-staff.md` "Tell a delivery time but from the terms of `help delivery-time`"; `topics/delivery-time-p2.md` "say so and state none; ask nobody and run no gate to measure it"; `topics/delivery-time-p2.md` "comes from the floor, said with its terms; without it, no time is promised" |
