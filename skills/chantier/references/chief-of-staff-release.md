# Chief of Staff: releases

## Releases

A release is a CR a Release driver runs by the project's own procedure; chantier holds none.
Find it in `AGENTS.md` and what it links (point to it in the `chantier` section); nothing
written, or a gap, is a question for the user and an offer to write the answer in the project.
A procedure silent on release notes or on an announcement is no gap: the release Driver then
follows [release-template](release-template.md). Offer to write the project's own version in the
project.
If the procedure has no long check on the exact head of the default branch before the version
commit, ask whether to plan one and say why: per-CR gates miss what CRs break together, and any
check skipped on a PR goes unseen. Offer to write the answer in the project. The user's answer
rules; chantier imposes no gate.
Prepare it as any CR (`$CHANTIER file "Release v1.4.0"`, grilled: the version when the user can
settle it, the scope, where the procedure is, what the user reviews). A release joins the batch of
the work it ships, best a stack batch: `--release N` at `open`, or `$CHANTIER order add --release
--note <folder>` in a running batch (one per batch, default grant; `order grant` after). It waits
for every other CR of the batch, the ones added later too (the CLI keeps its `after`; `order after`
is refused on it); in an ordered batch it is prepared on top of the stack once the others are
ready, in a parallel batch after the merges. When the user asks for a release in a parallel
batch, explain why it cannot be prepared before the merges (no branch holds all the work until
then) and recommend a stack batch instead; a parallel batch cannot be switched to a stack, so the
recommendation is for the batch being opened or the next one. The version is grilled at filing
when the user can; otherwise the Release driver picks it and says why: there is no version
confirmation. (chantier's own release joins the batch whose work it ships, as
`docs/release-process.md` says; that file ranks above this card as a project rule.) Write your
latest Progress report and the conversation excerpts you choose into the release CR's folder, as
`report.md` and `conversation.md` (the release Driver renders them from there, anonymised), when
the release joins the batch, and refresh them at each Progress report until the Release driver has
prepared the release PR. In the filing grill, ask whether a docs diagram should be shown in the
notes; only the user's yes puts one in, named in the release CR's specification. The user merges
the release PR (with the whole stack in an ordered batch, from the bottom up); record each merge
with `order merged`; that merge starts the release procedure.

The post-merge word is asked with the merge go:

- When: the release PR is offered to the user to merge, at the `ready-to-merge <release-cr>` ask
  (a parallel or series batch), or at the complete `stack-ready-to-merge` whose top is the release
  PR (a stack batch).
- What the ready line adds: in that same message, ask the user's word for each irreversible step
  the project's release procedure runs after the merge, each named on its own (for chantier:
  CONTRIBUTING.md "Release" step 4, `just tag`, and step 5, `gh release create vX.Y.Z
  --verify-tag ...`). The user may answer yes to all, yes to some, or nothing.
- What it leaves out: never the merge itself, which stays the user's, and never the announcement,
  which stays the user's and is never an agent's step.
- Recording a yes: before `order merged`, one `$CHANTIER order approve <release-cr> --note
  "<step>: user, <YYYY-MM-DD>: '<the user's words>'"` per step. When the user answers and merges
  in one message, the approvals come first, then `order merged`. In Foreman mode, send all the
  lines to the Foreman in one message.
- No word at the ready ask: nothing is recorded and today's path stays. The Release driver started
  at the merge hands back `blocked approval: <step>`, the approval ask follows, and the answer is
  `order approve`.
- A release redone before its merge (a `redo: <cr> <why>`, or a new attempt after a fix): the yes
  already recorded still holds (it covers the steps after the merge; the user's merge stays their
  review of the content), and nothing is recorded again. The next ready line for the version PR
  names the steps already approved (for example "already approved: `just tag`, `gh release
  create`"), read from the `approvals unused:` line of `$CHANTIER handoff <release-cr>`, and asks
  only for the steps with no yes yet, so the user can still say "wait".
- A "wait" on an approved step, said before the merge: write it at once in the release CR's
  `02-answers.md`, one line with the date, the user's words and the step. It is not an order and not
  a take (an `order note` on a ready CR is a take, and the Driver would restart before the merge).
  Then close the summary gap that the file's change opens ("A CR's summary"). When you record
  `order merged <release-cr>`, read that file; right after the merge, in the same relay (and the
  same message to the Foreman), record one note per step: `$CHANTIER order note <release-cr> --note
  "wait: <step>: user, <YYYY-MM-DD>: '<the user's words>'"`.
- A "wait" said after the merge is recorded the same way, as an `order note ... "wait: ..."`, at
  once.
- "auto": the "auto" tip and the approval question's "auto" answer stay as they are. Under a live
  grant, the steering session merges and there is no ready line to the user. Approvals already
  recorded before an "auto" stay whole: the grant's merge go spends none, so the Driver started at
  the merge still sees them. The post-merge steps go under the grant anyway.

With no release PR in the
procedure: once the other CRs are merged, ask the user whether to run the release procedure; the
yes is `$CHANTIER order confirm <release-cr> --note "<the user's word>"`. `order add` stays
refused once the release has started (a fix, `--fix-for`, accepted for urgent fixes, or the next
batch). The grant is the user's: by default each irreversible action waits for their approval (`order
approve`; an approval never lets the steering session merge a release PR); ask whether they allow more and pass only what they said (`--autonomous-releases
<n>`, `--grant-fixes`: the Foreman starts and merges up to three fixes, both with `--budget`;
later `order grant`).

While the release runs (from the start of its Release driver until `release published` or the
CR's end), offer "auto" as the "during a release" tip: one line with the exact word, e.g. "💡 Say
"auto" to let this release merge its release PR and run the irreversible steps of the procedure
without asking; the announcement stays a draft for you." On an approval ask (`ask ... blocked <release-cr> approval:
<action>`), the question to the user lists "auto" among its answers, beside approving that one
action (`order approve`, before or after the merge; `order confirm` stays only for a procedure
with no release PR): part of the question, not a tip, so it holds when tips are off. On
"auto" (the user's own word, in any language):
1. `$CHANTIER handoff <release-cr>`; read `<k>`, the releases already published, from its
   `grant:` line.
2. If the batch has no budget, ask for one with a recommended figure (the CLI refuses autonomy
   without it); send nothing before the answer.
   Then run `$CHANTIER preflight --autonomous-releases 1`, P9's probe 5 and the release trial; ask
   the question for the release rules still missing and act on the answer. The same for a later
   `order grant ... fixes=on` with `--grant-fixes`. The grant itself never waits for the rules:
   the user's word is the grant.
3. `$CHANTIER order grant <release-cr> --note "releases=<k+1>[ budget=<usd>]"`, and record the
   user's word with the date in the release CR's `02-answers.md`.
4. Send the order's line to the Foreman (direct mode: act on it yourself; a release CR blocked on
   an approval goes back to a Driver with `--note "auto: <the grant line>"`).
5. Tell the user in one line what auto now does (the steering session merges the release PR, by the
   GitHub route of [foreman](foreman.md), "Merging on GitHub", once
   every other CR is merged or cancelled, and the steps the procedure asks a go for, this release
   only) and what stays theirs (the announcement, posted by them; a fix, unless they grant it).

"auto" covers this release only: the next release asks again. It never covers posting an
announcement, starting or merging a fix (`fixes=` unchanged), the procedure's word
(`order confirm`) or a raise of the budget.

The publication refused by the host. The ask is `blocked <release-cr> approval: publish: <the
exact command>`. Give the user the command as a **For you** line, exactly as handed back, with
where to run it (the main checkout, or the clone `take` names with a planning surface): "the
publication is yours: run `<the command>`, then tell me when it is published". The question keeps
its usual answers ("auto"; the user's word that you run it yourself, each command alone, rule 9).
An `order approve` does not help here: the host refused the Driver, not the user. The user's word
that it is published ("done", in any language): relay it at once, `$CHANTIER order note
<release-cr> --note "publication done: user, <YYYY-MM-DD>: '<the user's words>'"`. In Foreman mode,
send the order's line to the Foreman; in direct mode, act on it as the Foreman's work: `take
<release-cr> --note "<the note>"` and a Release driver. If you ran the command on the user's word,
the same note follows once it has succeeded: `publication done: steering session, <YYYY-MM-DD>:
'<the user's words>'`. The Release driver then checks the publication and runs its end checklist:
its `release published` opens the "Released in" list and its `retro.md` reaches the Completion
report, both as below; the user is asked nothing more for this release, except what that list
already asks. Never relay a `publication done:` note the user did not give: no guess from the
forge, no silence read as a yes.

A refused main-checkout step: the line `release <cr>: <step> refused: <line>` from the Foreman, or
the refusal you see yourself in direct mode. Give the user a **For you** line with the refusal and
what it says to do ("the main checkout has tracked changes (...): commit or set them aside, then
tell me to run `just tag` again"); you never settle the checkout yourself. When the user says to
run it again: in Foreman mode, send `[chief-of-staff→foreman] release <cr>: run <step> again`, and
the Foreman runs it as its card says; in direct mode, run it yourself, the same way. The ready
ask's naming of the approved steps (CONTRIBUTING.md step 4, `just tag`) is unchanged.

`status` shows a `draft
<path>` on the release's line: give the user the link as soon as it appears. Once released,
read `work/retro.md` in the release CR's folder (`4-batch/3-done/`); it is offered once, in the Retro
of the Completion report at the pause that follows, with the batch's own points, each by its own
tag and route (a `project` point filed becomes an inbox item).

"Released in": once the release Driver has recorded `release published` (its note carries the
version and the link), list the issues the release ships, one line each: the issue's link and the
comment "Released in <the release's link>". The issues are the `issue:` lines of the CRs whose
merge the release contains: the batch's `4-batch/3-done/` folders and the `5-archives/` folders
merged since the previous release (`delivery.md` gives each one's PR and merge time). Show the
list; one yes from the user covers the whole list; post each as in "Ticket summary" step 7 (an
issue chantier cannot reach is skipped and said in one line). No issue in the list: say nothing. "auto" never
covers these comments.
