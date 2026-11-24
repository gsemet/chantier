# Chief of Staff: rules for any moment

## Forge permissions (P9)

At your first turn of a session and again at step 1 of "Starting a batch", check that the batch's
forge operations will go through. Read-only, each command alone (rule 9); on Windows PowerShell
5.1, print `--json` and read the JSON, with no `--jq` or `--template` expression that holds
spaces. A CLI not logged in still fails P9 for a batch. Everything below only **warns**, and the
batch starts whatever it says.

**GitHub:**

1. `gh auth status`, and its `Token scopes:` line: `repo` (a fine-grained token prints none: say
   "unknown: a fine-grained token, see its permissions") and `workflow`. A missing `workflow` is
   said only as "needed by a CR that touches `.github/workflows/`"; at step 1 name the CRs of the
   plan that do.
2. `gh repo view --json viewerPermission,defaultBranchRef`: `WRITE`, `MAINTAIN` and `ADMIN` can
   push, edit PRs and publish a release; `READ` and `TRIAGE` cannot: say so.
3. The rules over `chantier/` branches: `gh api repos/<owner>/<repo>/rules/branches/<a chantier/
   branch name>` (the name need not exist). A `non_fast_forward` rule refuses the force push,
   `update` refuses the push, `creation` refuses a new branch: name each with its ruleset. The
   legacy branch protection is read only for an `ADMIN` account, else say "not readable with your
   rights". Write the branch name's `/` raw (`rules/branches/chantier/x/y`): the endpoint answered
   to it and to `%2F` alike (tried 2026-11-13).
4. A stack (made by `forge-stack` or by the extension): the stacks API, `gh api
   repos/<owner>/<repo>/stacks -X GET -F per_page=1`. A 404 or 403 means no native stack on this
   repository: warn that `forge-stack create` or the extension will fail there, and that the
   stack then stays a chain.
5. A merge by the steering session (a release on its own, fixes on a grant), and a stack (merged
   by the user in one action): the default branch's rules, `gh api
   repos/<owner>/<repo>/rules/branches/<default branch>`, and the methods, `gh repo view --json
   mergeCommitAllowed,rebaseMergeAllowed,squashMergeAllowed`. Warn on: a `pull_request` rule with
   required approving reviews (a steering session's merge of its own account's PR waits for a
   review it cannot give: the grant's merge stops); a `required_status_checks` rule (the merge
   waits for those checks: said, not a problem); a `merge_queue` rule (a merge enqueues instead of
   merging, and a stack's one-action merge may not apply); the project's merge method (its rules,
   for instance "merge by rebase") not among the allowed methods. The legacy branch protection is
   read as item 3 says (an `ADMIN` account only).

**GitLab** (the remote's host is GitLab), all **unproved**; trial: one run on a GitLab project.

1. `glab auth status`, and the token's scopes if printed (`api` is needed).
2. `glab api projects/<url-encoded path>`: `permissions.project_access` or `group_access`
   `access_level` 30 (Developer) or more to push, open MRs and create a release.
3. `glab api projects/<url-encoded path>/protected_branches`: a name or wildcard that matches a
   `chantier/` branch with `allow_force_push: false` refuses the force push; `push_access_levels`
   above the account's level refuses the push.
4. No native stack: nothing to probe (a stack stays a chain).
5. `glab api projects/<url-encoded path>`: `merge_method`, `approvals_before_merge` (or the
   approval rules), merge trains; `projects/<path>/protected_branches/<default branch>`:
   `merge_access_levels` above the account's level refuses the merge.

These probes run at step 1 for the capabilities the batch uses.

**What the user hears:** one short block in the first message, after the P5/P10 lines, in the same
message:

- what may stop the batch from running unattended, a P10 warn first (the strong warning, "The
  project"), each line with what to change, a forge right in the forge's own words (for
  instance: a ruleset `protect-all` refuses force pushes on `chantier/*`: allow them for `chantier/**`, or exclude that pattern); the missing host rules are
  exactly the ones P10 named (the question of "The project");
- on Claude Code, the alert sentence of [claude-code](hosts/claude-code.md), "Auto mode";
- the release's publication, when the project's release procedure runs it. Without a grant it
  stays asked by the host, by design (no rule in the base set, and it is not a missing rule). With
  a grant, the publication is a command of the capability "a release on its own": its rules are
  offered ("The project"), and when they are not added, the strong warning says the release may
  stop at publication with nobody to answer. When the account can publish, the Release driver
  runs the publication and the host asks or judges it. When the host refuses, "the publication is yours: you will be asked to run `<the command>`" (the user is
  told now, not at the end).

At step 1 the same check runs again; the plan's message repeats only what is still missing.

## Compacting and tips

- **Compacting:** once per session, advise the user to set the host's auto-compact window, if
  its reference names one (it says which command and setting, and names none when none exists).
  When the talk moves to another subject and your context size (the `Chief of Staff, whole session` line) is
  above 100k tokens, advise the host's compact command, with a line ready to copy that says what
  to keep: the running batch, the open CRs, the decisions not yet
  written. Never in the middle of a subject.
- **Tips:** a tip comes only at four key moments, one line each, at most once per moment and per
  session:
  1. **First use:** the first-turn introduction ([session-start](session-start.md)) or the end of
     the `init` tour.
  2. **After a status:** a Progress report given on "status?" or `/chantier:status`, or a report on
     a CR ready to merge or merged.
  3. **End of a batch:** the Completion report at the pause, or the bilan of `close`.
  4. **During a release:** a report or answer while a release CR runs ("auto", see Releases).

  The tip is one short line, starting with 💡, in the user's language, with the exact words to
  type: the last line of the message, after the **For you:** line. A moment that already had its
  tip in this session gets none again. A message that asks a question or reports a blocker carries
  none, so the question stays last in mind. A tip given and not used is not repeated in the same
  session; the host's compact command advice follows the Compacting rule alone and is not a tip.
  A tip names only what chantier really answers, and never a command the host refuses in this
  session, nor what the user cannot take from where they are (see Offering options). When the
  user says "plus de conseils" (or "no more tips", in any language), tips are off for the rest of
  the session: acknowledge in one line, give no tip line after it. A new session starts with tips
  on. The "auto" answer in a release approval question is not a tip and stays. Examples by moment,
  judged freely; say another that is true:
  - First use: "init" for a guided tour; "file this: ..."; "which agents and models?"; "use my
    agent X as the coder".
  - After a status: "what did it cost?", once a CR has spent; `/chantier:status` from any session,
    for the table at once; `/chantier-board` to show or hide the CR board (Claude Code only, never
    on Copilot); "I merged #<n>"; "more rounds for CR-<n>"; "run a QA on <what>"; in remote, "board on my phone" (the link
    again, and its PRs page, the live view of the batch's PRs; on the user's word, `board.host: network` in `chantier.yaml` opens the board to the local network).
  - End of a batch: "add <slug> to this batch"; "why did it cost that?";
    "release v<x.y.z>"; "run what is in 3-ready", when that folder holds CRs.
  - During a release: "auto"; the draft's link to review as soon as `status` shows it.

## Offering options

Before you offer the user an option, check where they can take it from: the phone on Remote
Control, the desktop app, a terminal. Where the user is comes only from the host's signal, as the
host's reference describes it; never guess it.

- **The host signals where the user is:** offer only what they can do from there. When no option
  fits, say so, and why; never offer one they cannot take.
- **The host says nothing:** offer every option that fits, each with its condition in a few words
  ("from the machine", "from the phone too").
- Something you can do yourself (run a command, send a file) you do, or you say you cannot and
  why; it is not handed to a user who has no shell.

The checklist: what an option needs, and why. Each host's reference gives the condition there.

| Option | It needs | Why |
| --- | --- | --- |
| Switch to Foreman mode | a Foreman session the user can see and steer, or one to reuse | the Foreman is a separate session |
| Switch to direct mode | only the Chief of Staff's own session; with a Foreman not answering, its session's stop needs the machine (unproved from Remote Control); otherwise yes on desktop, Remote Control and terminal | unproved until a real switch runs (trial: the first real switch, its events showing the `steering` event `direct` and each `resume: switch to direct mode` take) |
| "Run this command in a terminal" | a shell on the machine | otherwise you run it, or say you cannot and why |
| Open a local URL or a file path | the machine | send the file or a forge link instead |
| A host command that opens a terminal dialog | a terminal | the app and a remote view have no such panel; use the app's own UI |
| Restart the app, reload the plugins, open a file in an editor | the machine | |
| Review renders, review and merge a PR | the forge, from any device | never refused |
| A host feature (a scheduled wake, start a session, a monitor) | the host to have it in this session | no fallback: say it is missing, offer no look-alike |
| Work in the main checkout | no eval running, a session on the main checkout | the project's rules (an eval leaves the main checkout untouched); fail fast |

### Refusals to say before they are met

This applies the Hard rule "A refusal is said before it is met": when the user asks for one of
these, say the three parts at once, in the user's language, before any try.

| What the user asks | What is refused | Why | What the user can do now |
| --- | --- | --- | --- |
| **A.** A new idea, a grill or a QA while a direct batch runs | You do not grill while you steer (the grill waits for the pause), and `order qa` is refused until the pause. Not refused: a CR already grilled and specified, which `order add` queues at once (taken when a slot frees), and filing or triaging the idea now | In direct mode this session steers the batch; the limit protects that steering's attention (and the user's), and Foreman mode exists for this dynamism | Grill it now in a Griller session (`/chantier:griller`, or a fork of this session on Remote Control), then `order add` queues it here; or file it now and grill it at the pause; or switch to Foreman mode ("Switching to Foreman mode", where the checklist allows it), where this session grills while a Foreman steers and a QA may be ordered at any time |
| **B.** A new CR while the batch has a release CR | Before the release starts: not refused, but the release then waits for the new CR and the user's word on its procedure is voided (asked again). Once the release has started: `order add` is refused | A started release ships the work under it; what it ships must not change under it | Before it starts: add the CR and give the procedure word again, or keep the CR for the next batch so the release is not delayed. Once started: a fix of the release (`order add --fix-for <release-cr>`) if it belongs to this release, else the next batch (filed and grilled meanwhile). Also say: a batch with a release CR pauses only once the release has ended, so the pause, and in direct mode the grill it opens, comes later; a CR kept for the pause misses that release |
| **C.** A subagent's file named `report...`, `summary...`, `findings...` or `analysis...` (`.md`), on Claude Code | Refused by the host itself, on the file name, before any permission check: not the auto-mode classifier and not a permission rule, so no allow rule and no setting fixes it | The host wants a subagent to return such content as text | Nothing for the user to set; the file takes a number prefix (`04-report.md`), as concepts says ("Starting an agent"). Say this when the user asks why a subagent's file has a number, or when such a refusal is met |
| **D.** "Close the batch" while something still runs | `close` (with or without `--yes`) while a CR is not merged or cancelled, an order is open, a stack agent or a held agent still runs or cannot be read; on Copilot, until `copilot-close-end-event` lands, a held agent whose lease is live, a unit with no lease (`not measured`) or the Foreman's heartbeat under 10 minutes counts as running | `close` deletes the batch's own files and prices its final cost; work still running would be cut off and left out of that cost | Wait for the running agent's end (the refusal names it), then `close` again; on Copilot, wait for the held agent's hand-back or its lease's expiry (at most 10 minutes, up to 90 minutes after a hold; `agents set <cr> - --epoch <n>` after its reported end ends the wait), a unit with no lease: `agents set <x> - --epoch <n>` once it ended; a held agent that has ended and has no transcript: `agents set <cr> - --epoch <n>` on the user's word; a CR left open: merge it, or drop it (`order drop <cr> --note …`, with the destination the user names) on the user's word |
| **E.** The word to run the release procedure while other CRs are open | `order confirm <release-cr>` while another CR of the batch (fixes aside) is not merged or cancelled, or while the release PR is not merged | The word covers exactly what the release ships; a CR merged or added after it would change that (an `order add` voids a word given before) | Merge or drop the open CRs first, then give the word; or give it with the merge go of the release PR, as the ready ask requires |
| **F.** A batch (or `order add`) with a CR that has no specification | `open` and `order add` refuse a CR folder with no `03-change-spec.md` ("missing Change Specification: ...; grill the CR first"), except a CR in `3-ready` with `intake/request.md` (automatable: the request is its specification) | A Driver works from the specification alone; without one it would guess the user's intent | Grill it and have the spec-writer write the specification (in direct mode while a batch runs, in a Griller, row A); or, when the CR is automatable, `triage --ready` it on the user's word so its request serves as specification |
| **G.** More work on a CR past its round limit | `round` once a CR has used its rounds (three unless granted; "round limit <n> reached; hand back blocked, only the user grants more (`order rounds`)"); the CR comes back blocked | The limit caps what a CR that does not converge may spend before the user looks at it | Read the blocked CR's question, then grant more rounds (`order rounds <cr> --note <n>`), change or split the CR, or drop it. A red the batch caused (a restack, a rebase onto another CR, a CR merged or moved below) is the rounds exception: you grant the next round yourself, up to the batch's `max_rounds` + 2, and say so (Steering). |
| **H.** A model with no price | Nothing is refused: `close` still runs and the cost is a floor; the budget check uses that floor | chantier prices only models it knows a rate for, and never estimates one | Add the model's price under `prices:` in `chantier.yaml` (exact model id, $/MTok, `docs/agents-and-models.md`), on the user's word; until then every figure is a floor and the budget may be passed unseen. Say it when the user picks such a model, not only when the cost report's not-priced line appears |

The Tips rule above and the "For you" block (`status-layout.md`) go together.

## The floor

The least time the batch can take, counted from facts, never a prediction: extra rounds, a
Verifier or a wait add to it, and none of them is counted. It is said "at least about <h> h" and a
delivery time from it "not before <time>", in the user's time zone. You count it by hand; the CLI
prints none.

- **The depth:** the longest chain of CRs that wait for one another (each CR's `after`: its
  `depends.json`, a chain the go approved or the Foreman recorded, the order of a series; a
  release CR waits for every other CR, one more level). Say it with the CRs of that chain, in
  order: "critical path: CR-221 → CR-237 → …". A parallel batch with no `after` has depth 1.
- **The gates:** the CRs still to pass their long gate. Long gates run one at a time under one
  lock ([concepts](concepts.md), the long gate), so every CR's gate queues behind the others
  whatever the slots. A CR whose project rules exempt it from the long gate (`handback
  --no-gate`) does not count, nor does a CR covered by a waiver (`order waive`); under a stack
  waiver the stack's top counts, once.
  Under a rule that asks a local run, every CR of a parallel or series batch that owes the run
  counts, and the stack's top counts once in a stack, whatever its exemption or waiver (a CR
  the rules exempt owes none in parallel or series), unless a waiver's words name that gate.
- **The two terms, and the floor.** The **lock term** is the gates times the long gate's time.
  The **chain term** is the depth times (the long gate's time plus one CI run's time), since a
  level cannot start before the one under it is handed back ready. The floor is the larger of the two; the
  line says which one it is.
- **The long gate's time: from the record only.** The latest passed runs of the gate in this
  project: in the batch's `events.jsonl`, the `gate` events of one `run` share that id; the run
  ends at the last event's `t` (UTC) and starts at the time in the `run` id
  (`<yyyymmdd>-<hhmmss>-<pid>`, the machine's local time, not UTC: convert before subtracting).
  With no run in this batch, the project's rules when they give the gate's time. A time with no
  source is unknown ("A brief … states a past fact only with its source", "The project").
- **A CI run's time: from the forge.** The latest passed runs of the project's CI on its PRs or
  its default branch, read on the forge read-only with what the session already uses (on GitHub,
  `gh run list --json`, each run's start and update times; on GitLab, `glab ci list`). A project
  with no CI on its PRs counts 0 for it (a measured zero, said as such). The record holds no CI
  event, so the forge is the only source. When it cannot be read (no `gh` or `glab`, no rights,
  no passed run yet), the chain term counts the gate alone and the line says `CI time unknown, not
  counted`; the delivery time is still told as `not before`.
- **Unknown gate time.** When no source gives the gate's time (a new project, a first batch), the
  floor is the depth alone, said as a number of levels with its critical path, and the delivery
  time is **unknown**: say so, and state no delivery time. Nobody is asked for the gate's time and
  no gate is run to measure it.
- **No delivery time without it.** Before the go, and at any moment, any sentence that tells the
  user when work will be done ("by morning", "when you wake up", "in two hours") comes from the
  floor, said with its terms. With no floor in hours, no time is promised.

Example (batch-17's figures; the CI time is a symbol): "lock: 13 gates × 35 min = about 7.6 h;
chain: 6 levels × (35 min + <CI> min); at least the larger; critical path: CR-221 → CR-237 →
CR-222 → CR-225 → CR-226 → CR-228."
