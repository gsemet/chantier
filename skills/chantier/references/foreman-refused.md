# Foreman: a Driver's refused force push or rebase

## A Driver's refused force push

A Driver's force push the host refuses climbs a ladder: the Foreman judges it and, when it is
legitimate, runs it; if the host refuses the Foreman (or the Foreman could not try), the Chief of
Staff judges it again and runs it, without asking the user; only if the host refuses the Chief of
Staff too is the user asked, one question, and the push runs once on the user's yes. Each session
that pushes judges first. In direct mode the steering session is the Chief of Staff: the ladder is
Driver, Chief of Staff, the user, with one judgement.

The route form, the one command of every steering-side push of this section, from the main
checkout, without changing its branch or touching its files:
`git push --force-with-lease=<branch>:<expected> <remote> <local sha>:refs/heads/<branch>`, or
`git -C <checkout> push --force-with-lease=<branch>:<expected> <remote> <local sha>:refs/heads/<branch>`
when the session's own directory is not that checkout (always with a planning surface: the
project's clone that `take` names). One command per branch, never a loop or a script, even for a
whole restack.

1. **Who reads it.** You, on a Driver's `[driver <cr>→foreman] push <branch> <expected remote sha>
   <local sha>` line; the Chief of Staff on yours ([chief-of-staff](chief-of-staff.md), "A refused
   force push") and, in direct mode, as the steering session. This is the one place of the check
   and the judgement.
2. **The check and the judgement.** The check, a hard refusal: the branch is covered (it matches
   `chantier/*`, it is not the project's default branch, and the push is `--force-with-lease`,
   never a plain `--force`: a CR carried from an earlier batch keeps its branch and is covered),
   so read the CR from the branch's last segment (`cr-115-…` is `CR-115`) and run `$CHANTIER
   handoff <cr>`; its `worktree: … branch <branch>` line must give exactly the branch on the
   line. Else push nothing. A branch that is not `chantier/*`, or the default branch, is never
   pushed, at any step: see "Not a chantier branch" below. The judgement, read-only (`git fetch
   <remote>`, then the main checkout or `git -C <worktree>`), on what it looks at, not a fixed
   list: the local sha is the worktree's committed head (`rev-parse HEAD`, a clean `git status`);
   the local head holds the remote head's work rebased onto the CR's base (the `base` that
   `handoff` prints: the default branch, or another CR's branch in a series or a stack): the base
   is an ancestor of the local head and the remote head's commits are in it (`git range-diff`, or
   `git cherry`); a patch changed by a resolved conflict is not by itself a doubt. The long gate
   passed at the local head: the last `gate` invocation at the local full sha in the batch's
   `events.jsonl` passed every command it was given (its events share a `run`), or the Driver's
   notes and last gate log in `handoff`; the stack driver's restack follows its own card. No gate
   pass at the local head is the Driver's slip, not a doubt: push nothing (the Driver runs the
   gate and sends the line again). When the `handoff` of the check prints the `ci: beside the long
   gate` line, a push with no gate pass at the local head is the mode's order, not a slip: skip
   this gate check (`handback ready` still enforces the gate at the PR's head). Likewise for a
   branch whose PR the record holds (`handoff` prints it): a push after a rebase with no gate pass
   at the local head is the early-push rule's order, not a slip ([driver](driver.md)): skip the
   gate check there too. Likewise when the project's rules name a pipeline job as the long gate:
   skip this gate check (the steering session checks that job at the PR's head; GitLab and
   Copilot: unproved). A branch with no PR yet keeps the gate check. A push that would drop work
   the remote has and the local head does not, or that you cannot tie to the CR, is not
   legitimate. The two refusals, a covered branch that `handoff` ties to no CR of this batch and no
   long gate passed at the local head (outside the skips): push nothing and take the CR back with
   `take <cr> --note "push: push refused <branch>: <the reason>"` (`not a branch of this batch`,
   or `no long gate passed at <local sha>`) by the restart path's steps, as for any answer (step
   8), with no hop to the Chief of Staff and no question to the user (in direct mode the Chief of
   Staff does the same).

   **Not a chantier branch:** a branch that is not `chantier/*`, or the default branch: push
   nothing, ever, at any step; take the CR back with `push: push refused <branch>: not a chantier
   branch` (step 8), and send `[foreman→chief-of-staff] push refused <branch>: not a chantier
   branch (<cr>)`, which the Chief of Staff tells the user as information (the report's shape: the
   branch asked and the CR that asked it, no question, no tip, nothing to answer). In direct mode
   the Chief of Staff does both. A user's yes does not push it.

   **A protected branch:** no session reads the forge's branch protection (no `gh api` or `glab
   api` rule). A push the forge rejects as protected (git's remote rejection: on GitHub
   `protected branch hook declined`; on GitLab `You are not allowed to force push code to a
   protected branch`, **unproved**) is not a failed lease: the session that ran it records
   `$CHANTIER note <cr> "push rejected by the forge <branch>: <git's text>"` and never retries it
   (step 7).
3. **Legitimate: the route rule first** (Claude Code; on Copilot, where P10 does not run, skip
   this step and go to step 4). Run `$CHANTIER preflight` and read its P10 line for "every batch"
   (the one whose text starts `every batch:`), as `commands/permissions.py` (`_gap`) and
   `commands/preflight.py` (`_check_allow`) print it. The route rule of the form you will run
   (`git -C * push --force-with-lease=chantier/* <remote> *chantier/*` for the `git -C` form,
   `git push --force-with-lease=chantier/* <remote> *chantier/*` for the plain form; `<remote>` is
   the project's remote as P10 fills it in, `origin` unless the project's configuration names
   another) counts as present unless:
   - that P10 line names it in an `(add …)` part, as printed: `(add Bash(<the rule>))`, or `(add
     Bash(<the rule>), PowerShell(<the rule>))` on Windows, the rule with the project's remote
     filled in; or
   - that line has a `denied:` part with an entry whose shortened command could be the route form
     you will run (P10 cuts a command of 60 characters or more to its first 57 and `...`, then
     writes `by <the rule>`, and ` (asks)` for an ask rule): then the rule counts as missing.

   Only the P10 line counts: the other preflight lines, the P10 line's broad or stale rules advice
   and the preflight verdict are not yours to act on here. (An unreadable settings file needs no
   reading of its own: a rule held only there is not found, so P10 names it in an `(add …)` part.)
   Missing: push nothing, record `$CHANTIER note <cr> "push not tried: route rule missing"` and
   send the `push` line of step 6 at once.
4. **Legitimate, the rule present:** first `$CHANTIER note <cr> "push judged legitimate at <local
   sha7> for <branch>: <one line: what the judgement checked>"`, then the route form, one command
   per branch. Accepted: take the CR back with `push: pushed <branch>` (the stack driver:
   `[foreman→driver stack] note push <branch>: pushed <branch>`) and send
   `[foreman→chief-of-staff] pushed <branch>` (information for the Chief of Staff's report; it
   answers nothing).
5. **Not legitimate:** push nothing; `$CHANTIER asks "<the CR, number and slug>: push <branch>
   <expected> <local> not legitimate: <what the judgement found>"` (the existing ask channel,
   relayed by the Chief of Staff to the user). The CR keeps waiting; the Chief of Staff answers
   `pushed <branch>` or `push refused <branch>: <the user's reason>` by the existing answer lines.
6. **The host refuses your push:** `$CHANTIER note <cr> "refused: <the exact command> -> <the
   host's exact text>"` first, then send `[foreman→chief-of-staff] push <branch> <expected remote
   sha> <local sha>`, not through `asks`. This is a named exception to the `refused <cr> <text>`
   ask (the asks bullet of "Your means") and to the user's allow line in your own chat ("The
   user's boundaries"): you wait for no allow line and ask the user nothing; the Chief of Staff
   takes it without asking. That line from you now means: judged legitimate, then refused to you
   or not tried (your notes say which). Retry nothing, try no other form, change no permission
   setting. Wait for the Chief of Staff's answer (`pushed <branch>`, `push failed <branch>
   <text>`, `push refused <branch>: <text>`) and take the CR back with it.
7. **A failed lease** (git rejects the lease: the remote moved) **or a push the forge rejects as
   protected** (above): never retried, at any step. Take the CR back with `push: push failed
   <branch> <git's text>` (the Driver looks at why) and send `[foreman→chief-of-staff] push failed
   <branch> <git's text>`; the Chief of Staff tells the user at once, with git's text (and, for a
   protected branch, that the branch is protected on the forge), and nobody waits for a word.
8. **The answer's way back.**
   - The answer does not go to a live Driver as a note: the Driver handed back `blocked waits: push
     <branch> …` and ended. When the CR is `blocked` with that `waits:`, take it back at once with
     the restart path's steps (the id cleared first: `agents set <cr> - --epoch <n>`) and `take <cr>
     --note "push: <the answer, as it came>"`, then a new CR Driver (or Release driver), before
     any queued CR: a blocked CR holds no slot, so it takes the next free one, as for a `context:`
     hand-back. No round is counted.
   - An answer that comes before the hand-back has landed (the CR still `working`): wait for the
     hand-back, then take it back as above. A Driver that ended without its hand-back takes the
     lost-Driver path, with the answer in its `resume:` note.
   - A Driver of a CR handed back `waits: push` is never pinged, and the CR is not a lost Driver
     (it is `blocked`, not `working`). The stack driver, which waits for the push result, still
     gets `[foreman→driver stack] note push <branch>: <the answer>`.
9. **Record each refusal once, whoever sees it:** the Driver's (before its push line,
   [driver](driver.md)), yours (step 6, or the `push not tried` note of step 3), the Chief of
   Staff's; each before the next step's line.

## A Driver's refused rebase

A Driver's rebase the host refuses climbs the same ladder as its force push: the Foreman checks it
and runs it, then, if the host refuses the Foreman (or the rule is missing), the Chief of Staff
([chief-of-staff](chief-of-staff.md), "A refused rebase"); the user is asked only if the host
refuses the Chief of Staff too, one question, and the command runs once on the user's yes. In
direct mode the ladder is Driver, Chief of Staff, the user. This is a named exception to "no `git
rebase`" (the early-conflict check, "Your means"): only this command, only in a Driver's worktree,
only on such a line. The steering session resolves nothing.

1. **The check, a hard refusal.** On `[driver <cr>→foreman] rebase <branch> <base>`: the branch is
   covered (as in the push's step 2: `chantier/*`, not the default branch), the CR is read from
   its last segment, `$CHANTIER handoff <cr>`'s `worktree: … branch <branch>` line gives exactly
   it, and the line's `<base>` is the `base` that `handoff` prints. Else rebase nothing: take the
   CR back with `take <cr> --note "rebase: rebase refused <branch>: <the reason>"`.
2. **The rule first** (Claude Code; Copilot skips it), as step 3 of the push: the P10 `every
   batch:` line names in an `(add …)` part, or under `denied:`, the rebase rule of the form you
   will run (`git -C * rebase origin/*`, `git -C * rebase chantier/*`, `git -C * rebase --onto
   …`, with the project's remote filled in): rebase nothing, record `$CHANTIER note <cr> "rebase
   not tried: rule missing"` and send the line of step 4 at once.
3. **Run, one command:** `git -C <worktree> rebase <base>` in the Driver's worktree, the worktree
   clean (a clean `git status`), after `git -C <worktree> fetch <remote>`. A clean rebase: note
   `rebased <branch> onto <base> at <sha7>` and take the CR back with `rebase: rebased <branch>
   onto <base> at <sha7>`. A conflict: leave the rebase stopped (no `--abort`, no resolution),
   take the CR back with `rebase: rebase conflict <branch> onto <base>`. Never `--exec` or `-x`.
4. **The host refuses you:** `$CHANTIER note <cr> "refused: <the exact command> -> <the host's
   exact text>"`, then send `[foreman→chief-of-staff] rebase <branch> <base>`, not through
   `asks`; wait for the answer (`rebased <branch> onto <base> at <sha7>`, `rebase conflict
   <branch> onto <base>`, `rebase refused <branch>: <text>`); retry nothing, try no other form,
   change no permission setting.
5. **The answer's way back** is the push's step 8, with the note `rebase: <the answer, as it
   came>`; the Driver's hand-back was `blocked waits: rebase <branch> <base>`. Record each refusal
   once, whoever sees it.
