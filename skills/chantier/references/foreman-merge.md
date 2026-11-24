# Foreman: a hand-back, a merge

## An order merged, by mode

- On an `order merged <dependency>` (the user's or your own), each CR handed back ready as a
  PR in draft waiting for that dependency, whose dependencies are now all merged, goes back to a
  Driver at once: `take <cr> --note "rebase: <dependency> merged"`, then the Driver that handed
  it back resumed as below (it takes a slot, or waits like any queued CR when none is free). One still waiting for another open
  dependency is rebased onto that one and stays a draft: the note says which. This holds in every
  mode. Then, by mode:
  - **Parallel:** every CR with a PR still open goes back to a Driver (its state is the one from
    the `status` read just before sending a note, [foreman](foreman.md), "Your means"): a CR handed back `ready` or `blocked`
    with `take <cr> --note "rebase: <merged cr> merged"` (a slot, or it waits like a queued CR
    when none is free; one handed back `ready` resumes its Driver as below, a `blocked` one gets a new CR
    Driver); a `working` one gets `[foreman→driver <cr>] note rebase:
    <merged cr> merged`; it rebases once, before its next push. Conflict or not, its checks run again at the new head. A queued CR needs
    nothing.
    When the CR this rebase `take` goes to owes the local run (as "The user's boundaries" says)
    and holds no passed or carried long gate at its new head, the same `take` carries the gate
    note: `take <cr> --note "rebase: <merged cr> merged; long gate: this CR runs <command>
    locally"`; no separate gate `take`.
  - **Series:** the CR whose predecessor merged goes back to a Driver with `take <cr> --note
    "rebase: <cr> merged"` (or the `note` line, by the state from the `status` read just before
    sending a note, as in the parallel line) and turns ready to merge on the default branch.
    When the CR this rebase `take` goes to owes the local run (as "The user's boundaries" says)
    and holds no passed or carried long gate at its new head, the same `take` carries the gate
    note: `take <cr> --note "rebase: <merged cr> merged; long gate: this CR runs <command>
    locally"`; no separate gate `take`.
    Whenever a CR's branch moves (a
    rebase, a new round after review), the started CR above it goes back to a Driver with
    `--note "rebase: <cr> moved"` (or the `note` line, when it is working), and stays a draft on
    that branch; each one moved this way moves the next.
  - **Stack:** see [foreman-stack](foreman-stack.md), "After a merge".
  - **A Driver merged under it:** a Driver's line `[driver <cr>→foreman] … <cr> is merged: no
    Driver to hand it back …` (with its note of what it left undone) is not an anomaly and not an
    ask: read the Driver's note (`log <cr>`), and when it names work still needed on the default
    branch, pass it to the Chief of Staff in one line (`[foreman→chief-of-staff] merged early
    <cr>: left undone: <the note>`), who offers it to the user as an inbox item. Nothing else: no
    `take`, no restart. The CR's worktree and branch are removed by the CLI's cleanup at the
    end of the last CR, never while its Driver may still run.

## The main checkout after a merge

- **The main checkout after a merge.** On by default in every project, unless the project's rules
  forbid it; a convenience, never a gate: a skip costs the batch nothing, asks nothing and has no
  workaround. It is yours alone (a Driver, a worker and, in Foreman mode, the Chief of Staff never
  do it), by git; the CLI runs no fast-forward (it removes, at the batch's end, only the merged
  CRs' worktrees and branches). For the last merge the order is already marked done by the
  pause; the fast-forward still runs right after it, with its `main checkout:` note.
  - **When:** right after you handle the Chief of Staff's `order merged <cr>` line, before you
    mark that order `order done`, and right after your own `order merged <cr> --epoch <n>`.
    Several merges handled in one turn get one attempt after the last of them. The order of the
    other steps after a merge (rebase notes, `take`) is unchanged.
  - **Which checkout:** the main checkout, where you run; with a planning surface, the project's
    clone (the one `take` names), by `git -C <clone>`, never the surface's checkout. Below, `git`
    means that, `<remote>` and `<default>` are the project's (the `--default-branch` given to
    `open`).
  - **The steps,** stopping at the first that says no; each "no" is one line, its `<why>`:
    1. The project's rules (`$CHANTIER rules`) forbid changing the main checkout now: do nothing.
       `<why>` = `the project's rules forbid it: <the rule, quoted short>`.
    2. `git symbolic-ref --quiet --short HEAD` is not `<default>` (another branch, or a detached
       HEAD): do nothing. `<why>` = `on <branch>, not <default>` (or `detached HEAD`).
    3. `git status --porcelain --untracked-files=no` is not empty: do nothing. `<why>` =
       `tracked changes: <up to three paths>`. Untracked files are never listed, read, moved or
       deleted.
    4. `git fetch <remote> <default>`. A failure: do nothing. `<why>` = `fetch failed: <git's
       text>`.
    5. Note `git rev-parse HEAD` as `<before>`, then `git merge --ff-only --no-overwrite-ignore
       <remote>/<default>`, only this form: never `git
       pull`, `reset`, `rebase`, `stash`, `clean`, `checkout`, `switch` or a merge without both
       flags. It succeeds: done, `fast-forwarded to <sha7>` (the new `HEAD`), or `already at
       <sha7>` when there was nothing to bring. Git refuses it: do nothing more, retry nothing;
       `<why>` = git's reason in a few words (`diverged from <remote>/<default>`, `untracked
       file in the way: <path>`, or git's text). The host refuses the command: do nothing more,
       try no other way; `<why>` = `refused by the host: <exact text>`. `--no-overwrite-ignore`
       is load-bearing: without it git overwrites an ignored file the incoming commits add.
  - **The line:** record the outcome on the CR whose merge you just handled (the last one when
    several): `$CHANTIER note <cr> "main checkout: fast-forwarded to <sha7>"`, `"main checkout:
    already at <sha7>"` or `"main checkout: not fast-forwarded: <why>"`, with no `--epoch`. No ask,
    no message: the Chief of Staff reads the note for its next report. The CR's state is
    unchanged. After a fast-forward, when `git diff --quiet <before> HEAD -- uv.lock` says
    `uv.lock` changed (exit 1), the note is `main checkout: fast-forwarded to <sha7>; uv.lock
    changed: sync pending`: you never sync, the Chief of Staff does (chantier's own checkout, when
    the session's project is chantier: the dev mode).
  - **After:** no reload of the plugin, no new reading of the cards (the CLI is read live; the
    cards load at the next session or with `/reload-plugins`). The next merge recorded tries
    again from step 1.

## Merging on GitHub

- **Merging on GitHub** (a release PR or a fix PR, under the grant, after `release go` says `go`;
  GitLab has no native stack and `glab mr merge` stays; the route is **unproved** by an agent, on a
  Copilot host too, until a real run). GitHub refuses `gh pr merge` for a PR of a native stack. In
  direct mode the Chief of Staff follows the same route.
  1. Read the stacks: `gh api -X GET repos/<owner>/<repo>/stacks -F per_page=100`; find an open
     stack (`open: true`) whose `pull_requests` holds the PR among its open ones.
  2. None holds it: `gh pr merge <pr> --<the project's method> --match-head-commit <head SHA>` (head
     from `gh pr view <pr> --json headRefOid`).
  3. A stack holds it and an open PR sits below it: do not merge (the asynchronous merge takes every
     open PR below it). Ask `[foreman→chief-of-staff] release <cr>: PR <pr> is in a stack above open
     PRs <numbers>; not merged`; in direct mode the Chief of Staff tells the user.
  4. A stack holds it and it is the lowest open PR: `gh api -X PUT
     repos/<owner>/<repo>/pulls/<pr>/merge-async -f merge_method=<rebase|squash|merge, the project's
     method> -f merge_action=direct_merge -f sha=<head SHA>`. Its `status`: `merged`: go on (`order
     merged`, the fast-forward). `pending`: one wait of at most 30 s (concepts, rule 8's second
     exception), then one `gh api -X GET repos/<owner>/<repo>/pulls/<pr>/merge-async/<details.uuid>`;
     `merged`: go on; still `pending`: no new `PUT`, no loop, `$CHANTIER note <cr> "merge: <pr>
     pending on GitHub's asynchronous merge after <s> s"` and ask `[foreman→chief-of-staff] release
     <cr>: merge of PR <pr> still pending on GitHub`; before any later attempt read `gh pr view <pr>
     --json state,mergedAt`: a merged PR is recorded, never merged again. Anything else, or a
     refused call: a stop, reported with its exact text; no other route, no `gh pr merge`.
  The head SHA in both forms guards that the merged head is the one judged.

## A CR taken back from ready

- A CR taken back from `ready` (every `take <cr> --note` above, the Series one and the PR ready to merge
  that stopped merging included) is run by the Driver that handed it back:
  - Note the Driver's agent id first (`status`; it may be the same read as the one before the
    note, so do not run it twice), then `agents set <cr> - --epoch <n>`: `take` refuses a CR
    with an agent recorded. When no id is recorded (the Driver was stopped after its hand-back, "An ended Driver that
    wakes again"), `take <cr> --note "resume: <the take's note>" --epoch <n>` and start a new CR Driver
    from the skeleton it prints, then `agents set <cr> <id> --epoch <n>`; the resume steps below do not
    apply.
  - The `take` comes next: it holds the slot, or makes the CR wait for one like a queued CR when
    none is free.
  - Then resume that Driver (the agent id you noted): send
    it `[foreman→driver <cr>] note taken back: <the take's note>` by the host's means (your host's
    reference), and record it again with `agents set <cr> <id> --epoch <n>`, so the log shows
    the resume.
  - It does not answer (the host refuses the message, or no `[driver <cr>→foreman]` line from it
    by the next heartbeat wake): `agents set <cr> - --epoch <n>`, then a new CR Driver as for a
    Driver that ended without its hand-back, with `take <cr> --note "resume: <the take's note>"`
    (the CR is `working`: no new slot).
  - A CR taken back from `blocked` keeps a new CR Driver.
  - A `[driver <cr>→foreman] hand-back ready … it was blocked: …` comes from a blocked CR whose
    Driver was still recorded (a `waits:` that landed, a `question:` answered to it, an `infra:`
    that cleared): the CLI accepted it after its usual checks, the CR is `ready`, and it needs no
    `take`. Handle it as any ready hand-back. A release stays `blocked` until `take <release>
    --note`.
