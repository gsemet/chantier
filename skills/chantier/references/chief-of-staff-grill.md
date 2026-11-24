# Chief of Staff: backlog and grill

## Backlog and grill

```bash
$CHANTIER file "<raw request>" [--title "<short title>"] [--slug <slug>]   # or @<file> for a raw request file
$CHANTIER triage <inbox-or-backlog-folder> --priority P1|P2|P3|P4   # a backlog item changes priority
$CHANTIER triage <inbox-or-backlog-folder> --ready    # to 3-ready, for the next batch, on the user's word
$CHANTIER triage <inbox-or-backlog-folder> --running-batch   # mark a grilled CR for the running batch
```

`triage --ready` only moves the folder: `3-ready` always means the next batch, and it joins no
batch. `4-batch/1-pending/` is the running batch: a CR reaches it by `open` or by `order add`,
never by `triage`. `triage --running-batch` writes the mark `work/running-batch` (the time and the
open batch's id) on a grilled CR of the inbox or the backlog, and moves nothing; any other
`triage`, `abandon` and `order add` clear it. `status` names the marked CRs (`running batch:
...`) and each stale mark (one naming a closed batch: `triage <folder> --ready`). See "Where the
CR goes" below.

```bash
$CHANTIER abandon <unclaimed-folder>                  # only on the user's explicit word
$CHANTIER restore <6-trash/item> [--slug <slug>]      # only on the user's word
$CHANTIER summary lint [<folder>]                     # the CRs whose summary is missing or late, each with its command
$CHANTIER summary set <folder> --title "…" --summary "…"   # what you wrote; --unchanged when it still holds
$CHANTIER summary label <folders> --add|--remove <labels>  # on the user's word only
$CHANTIER summary group <folders> --name "…"|--clear  # on the user's word only
```

A backlog CR left waiting for the user's answer between two grills gets `$CHANTIER wait <folder>
add answer --ref "<the question>" --note "<why>"`, cleared (`wait <folder> clear <id>`) once the
answer is recorded in `02-answers.md`; its open waits join the batch's record with it.

A CR's summary ([concepts](concepts.md), "A CR's summary") applies to your own writes too
(`01-intent.md`, `02-answers.md`, the ticket summary's records): run `summary lint <the CR's
folder>` before you end the turn, and close its gap with `summary set`. The sweep: `summary lint`
with no folder, and its gaps closed, whenever you re-read the backlog's folders (before proposing
a batch, on "status?", when the user says a Griller has finished), after placing a Griller's files
from a worktree, after a `restore` (it appends to `01-intent.md`), and after `close --yes` (the
archives' `delivery.md`). Its first line carries the count and the output stops at ten lines: run
it again until the first line says `no gap`. A named archive folder is checked; the default walk
leaves `5-archives` out.

`file` keeps the request as received in `intake/request.md`. A CR is filed with a short title (at
most 72 characters), the description below it: `file` refuses a request without one unless `--title`
is given. Write `01-intent.md` and record every
answer in `02-answers.md`. Grill at any stage, once for all the CRs of a batch, item by item: skip
a question whose answer would not change the specification. Each question carries your
recommendation, in the format below. Only the user sets priorities and picks what runs.

**Another project's CR.** In a surface with several projects, a CR of another project is that
project's.

- A relay is allowed on the user's word: the skill's command with that project's `--project
  <absolute folder>` for that `file` alone; `$CHANTIER` keeps the session's own `--project`.
- `file` prints its usual `filed <folder>; write the intent and grill the CR here`, unchanged; for
  another project's CR its "grill the CR here" is not followed.
- Say instead, in one line, that the CR waits for that project's own Chief of Staff or Griller;
  offer no grill, specification (`spec-writer`, `spec-critic`), `triage`, batch or `order` for it.
- After the relay, nothing more: no `01-intent.md`, no `summary set`. This is an exception to the
  summary rule of the paragraph above ("A CR's summary ... applies to your own writes too") for the
  `intake/request.md` that `file` wrote: the other project's own Chief of Staff or Griller writes
  the intent and closes the summary.
- Only the user's explicit word for that CR ("grill it here") lifts the default: for that CR's
  whole path in this session, its grill, its specification (`spec-writer`, `spec-critic`) and its
  `triage`, with the skill's command and that project's `--project`. A launch (`order add`, a
  batch, `open`) stays outside that word: it needs the other project's batch.

#### Asking the user: a series

- **Who:** the Chief of Staff and the Griller, for every grill and specification question,
  including a specification's open questions and the closing "grilled enough?". Not the Release
  driver's yes/no confirmation before an irreversible action, nor the card's other questions (a
  release approval with "auto", a force-push question, "looks stopped"): those keep their shapes.
- **One asker per item:** one session grills an item at a time; another session waits or takes
  another item. (Grillers take no lock, [griller](griller.md), "From the files": this is agreed
  between the sessions, through the user, not enforced.)
- **One item per call:** never two CRs in the same call of the question tool. One call is about
  one CR or backlog item; questions about another item go in a separate call. A series may touch
  any facet of its item (scope, words, icons).
- **The series:** independent questions only, as many as the host's question tool takes, never
  more than 5; the host's reference gives its figure.
- **The short name:** before an item's first series, read the head of its `02-answers.md`. With no
  ``Short name: `<name>` `` line there, pick a short name (a few words, e.g. `grill-format` for
  `250-grill-question-format`; it need not be the folder's name) and write that line at the head
  of `02-answers.md` (creating the file if needed) before the series is shown. With the line
  there, use it unchanged: the name is kept for the item's life, whoever asks next. It is used
  only inside question references, never as the CR's name.
- **The reference:** each question carries `<short name>-Q<n>`, e.g. `grill-format-Q3`, even when
  the CR has a number (never `CR250-Q3`). `<n>` keeps counting across the item's series: read the
  last reference in its `02-answers.md` before a new series (a second series after Q1 to Q7
  starts at Q8). The list number of an answer there need not match its Q number. The reference
  names the question only: the context, and anything else that names the CR (status, PR,
  `depends.json`), names it by number and slug as [concepts](concepts.md) says ("CR-250
  grill-question-format").
- **The text first, every time:** every call of the question tool is preceded by its text,
  without exception: the first series of an item and every later one, a single question, the
  closing "grilled enough?", a specification's open questions, on every host and surface (Remote
  Control from a phone included: the user scrolls up to read it). That message gives, for each
  question in order: its reference and the question; a short context (two or three lines: the CR
  by its name, why this point matters); the options, lettered `A.` to at most `D.`, each with a
  clear, concrete example of what it would mean in use (examples help the user most); and the
  reason for the recommendation. No call goes out without it, and never with the references left
  out of it.
- **The options:** at most 4 per question, the 4 most plausible; the text says the tool's own free
  answer ("Other", whatever the host calls it) is there for anything else. The recommended option
  is always `A.`, marked "(recommended)" in the user's language (e.g. "(recommandé)"), on both
  sides.
- **The same on both sides:** the tool then shows the same questions, in the same order, each
  starting with its reference, and the same options in the same order, each starting with the same
  words as in the text (`A. <words> (recommended)`). The form is the short mirror of the text: the
  text says more than the tool (the context, the examples, the reason); never other words,
  another order or another option.
- **No question tool** (a host or surface that truly has none; none is known today): the same
  text, ending with how to answer: by reference, in one message, e.g. "Q1 A, Q2 B" (a free
  answer is accepted as ever).
- **The record:** each answer goes into `02-answers.md` at once (as "Record at once" says),
  starting with its reference, e.g. `9. grill-format-Q9: **Numbering.** <the answer, with the
  user's words>`.
- **"Grilled enough?"** After the complete restatement ("Shared understanding"), the question is
  asked in the same format: its reference, its options with the recommended one first as `A.`,
  and the reason. With a batch open (running or paused, not closed), four options: `A. Specify,
  for the next batch (3-ready) (recommended)`, `B. Specify, for the running batch <batch-id>
  (4-batch/1-pending/)`, `C. Back to the backlog`, `D. Not yet`. With no open batch, B is not
  offered and the CR is for the next batch: `A. Specify, for the next batch (3-ready)
  (recommended)`, `B. Back to the backlog`, `C. Not yet`. The answer A or B is also the
  destination of "Where the CR goes" below.

A worked example, one item (`ready-wording`, CR-231 ready-line-wording), two questions. The text
written first:

```text
ready-wording-Q1 - Which words open the ready line?
Context: CR-231 ready-line-wording. The line is the first thing the user reads after a batch.
A. Name the CR first (recommended). Example: "CR-231 ready-line-wording: PR 52 ready".
B. Name the PR first. Example: "PR 52 ready (CR-231 ready-line-wording)".
C. Count first. Example: "3 of 4 ready: CR-231 ...".
Recommendation: A, the CR is what the user knows; "Other" is there for anything else.

ready-wording-Q2 - Does the line quote the known gaps?
Context: CR-231 ready-line-wording. Gaps decide whether the user merges.
A. Yes, quote them (recommended). Example: "... PR 52 ready, gap: no screenshot".
B. No, link the PR only. Example: "... PR 52 ready".
Recommendation: A, a gap left out is a surprise at the merge.
```

Then the tool call, the short mirror (same references, order and first words):

```text
AskUserQuestion
  ready-wording-Q1: A. Name the CR first (recommended) | B. Name the PR first | C. Count first
  ready-wording-Q2: A. Yes, quote them (recommended) | B. No, link the PR only
```

The Change Specification is the `spec-writer`'s ([`spec-writer.md`](spec-writer.md)), not yours.
On the user's word that a CR is grilled enough, write `work/specifying` in its folder (one line:
the time and the agent id), then, for a CR bound for the running batch, run `$CHANTIER triage
<folder> --running-batch` (the mark; a CR bound for the next batch carries none), then start the
`spec-writer` in the background (you or a Griller starts it), at any time, a batch running or not; its prompt names the card and the CR folder, and
its first line is the one `$CHANTIER playbook` prints (`spec-writer prompt, first line: …`), or
the Spec-writer's line of "Starting an agent": copy the first line, unchanged. The project sets how many CRs
are specified at once (`specifying.parallel`, 4 unless a `chantier.yaml` or the board's Configuration page, Limits tab,
says otherwise): `$CHANTIER playbook` prints it in its `limits:` line (`specifying <n>, markers <m> (<CR folders>)`), the `m` CRs
being those with a `work/specifying` in the inbox, `2-backlog/P1`..`P4` or `3-ready`. When `m` has reached `n`
(`specifying at the limit` ends the line), start no new spec-writer: tell the user which CRs are being specified, and start
that one when one of them is shown or dropped; a user's `specifying.parallel` of 1 means one CR at a time. A critic or a next
run on a CR whose marker exists is no new CR and is not counted twice. `work/specifying` is the guard of one spec-writer per CR: write
it before the start (the time), add the agent id once started, and while it exists start no
spec-writer on that CR. A first-line refusal ends that agent: replace the line with `<time> <new
agent id> restart: refused first line` and start one new spec-writer by copying that line, no
message to the refused one and no variants. A spec-writer ended by a host failure: the same, once,
with `restart: host failure: <text>`. Remove `work/specifying` when the (last) one ends, whatever
the result. Review `03-change-spec.md` against `02-answers.md` before you show it:
nothing dropped, nothing invented. Its open questions go to the user; record the answers in
`02-answers.md`, then run the writer again (and see "The spec critic", below, for an impactful
CR). A CR moves to `3-ready` (`triage --ready`)
only on the user's word, specified or not; until then it stays in the inbox or the backlog. A
`3-ready` CR keeps no priority: it is one flat set, the next batch's candidates (`triage
<3-ready-folder> --priority Pn` puts it back in the backlog). The spec-writer and the spec critic
take no slot and no budget of any batch; their cost is on the `grill and specifications with the
user` line. A release CR's and a fix's specification stay yours; the spec critic runs on them too
when you judge them impactful, by the criterion below: with no grill, you judge once you have
written the specification and say the critic line in the message that would show it (the user may
flip it); you apply the fixes yourself (step 4 below, without the spec-writer), then the user sees
the summary line and the questions as step 5 says. A ticket (Jira, GitLab, GitHub): read it with what the project has, and `file` it as
received, with its link: write `issue: <link>` under the title of `01-intent.md` (as
[concepts](concepts.md) says), and add it later if the grill reveals the issue. A Jira ticket's link is its browse URL
(`https://<site>/browse/<KEY>-<n>`).

Where the CR goes. A CR grilled enough goes to the next batch (`3-ready`, the default) or, when a
batch is open (running or paused, not closed), to the running batch (`4-batch/1-pending/`), in
every mode (parallel, series, stack):

- **Asked at every spec-writer start**, yours or a Griller's, with the same two options in the
  series format (`A. Next batch (3-ready) (recommended)`, `B. Running batch <batch-id>
  (4-batch/1-pending/)`), when a batch is open. The answer A or B of "grilled enough?" is that ask
  for the start it triggers; a start with no such answer just before it (a CR grilled in an
  earlier session) asks it on its own. With no open batch nothing is asked: the CR is for the next
  batch. A next run on the same CR (after the critic's fixes, or after open questions are
  answered) keeps the destination already recorded and asks only when none is recorded.
- **Recorded** in `02-answers.md` at once, with the critic's yes or no, e.g. `Destination: next
  batch (3-ready).` or `Destination: running batch batch-12.`
- **That answer is the user's word for the move**, and for the running batch it is also the go.
  The specification is final when `03-change-spec.md` is written, no spec-writer runs on it, its
  critic, when due, has run and been applied, and no open question remains (its answers recorded
  and the specification rewritten). Then, with no other question: for the next batch, you (or the
  Griller that ran the grill) run `$CHANTIER triage <folder> --ready`; for the running batch, you
  run `$CHANTIER order add --note <folder>` and handle the order as usual (Foreman mode: relay its
  line to the Foreman; direct mode: take the CR when a slot frees). A Griller never runs `order`.
  The destination acted on is the last `Destination:` line of the CR's `02-answers.md`, whether
  the grill wrote it or a board line did (see "A watcher's notification or end"): `Destination: next batch ...`,
  `triage <folder> --ready`; `Destination: running batch <batch> ...`, `order add --note
  <folder>`; `Destination: back to the backlog (board)`, no `triage` and no `order`: the CR stays
  in its inbox or priority row (the user's move put it there).
- **`order add` refused:** a release has started in the batch (rule B), or the batch closed while
  the CR was being specified: run `triage <folder> --ready` (it clears the mark) and tell the user
  in one line, e.g. `<slug> goes to the next batch: a release started in <batch>`. The writer not
  running: restart the server as that refusal says; the CR waits, still marked, then joins with
  `order add`.
- **A `3-ready` CR is never marked.** When the user wants an automatable `3-ready` CR, or one with
  its final specification, in the running batch, run `order add --note <folder>` at once.

Record at once: every human answer and decision about a CR goes into that CR's `02-answers.md`,
with the date and the user's words, right after it is given: before the next question, before
any other work, in the same turn. This covers decisions given outside a grill (a priority, "left
aside", "same batch", "later"). A grill round with several answers is one write per CR touched.
Nothing waits in the conversation only.

Grillers write the CR folders too: re-read the backlog's folders before proposing a batch, on
"status?", and when the user says a Griller has finished; re-read a CR's folder before each act
on it. Files from a Griller in a worktree (`files for <slug>: <paths>`): read them, place them in
the CR folder of the planning folder as received (a new item through `$CHANTIER file @<its
request>` first), tell the user (the worktree may be removed only after you have placed its files),
and review a specification as one from the `spec-writer`.

A CR's artifacts during a grill follow [concepts](concepts.md), "A CR's folder holds its work":
prototypes and experiments go in the CR's folder; a new version of a prototype is a new
`prototypes/NN-<idea>/` (the earlier ones stay); the user's choice of the retained version is
recorded in `02-answers.md` at once like any answer (e.g. "Retained prototype:
`prototypes/02-<idea>/`"). Leaks you close during a grill: an image the user pastes in the chat (no
file exists) is asked for as a file and saved in `evidence/`, or, if the user does not give it,
described in `02-answers.md`; a built-in browser screenshot kept as proof is saved on purpose in
`evidence/`; web research keeps its sources and quotes in an `experiments/` note; a claude.ai
artifact or an inline visualization that matters to the CR has its source saved in
`prototypes/NN-<idea>/` (its link, if any, in that version's `README.md`); a plan-mode plan about
the CR is written in the CR's folder; your memory is never a CR's place (decisions go to
`02-answers.md`, as "Record at once" says).

**With a planning surface** ([concepts](concepts.md)): the surface's own rules win for what they
say, its `AGENTS.md` first; its writer commits and pushes the plan (the `writer` action). A clone missing at
`checkout.yml`'s path (`preflight` fails naming it) is cloned on the user's word. Outside
contributors submit a CR by a PR on the surface, which the user reviews and merges on the forge;
a CR so merged into `1-inbox` or `2-backlog/P<n>` is read like any other. Never touch the
project's clone except by `git -C <clone>`.

**An outside PR** (merged on the project without chantier), only on the user's word, "archive
<link>": never offered unprompted, never from a forge read of your own.

- In a planning surface, read the `writer:` line first (`$CHANTIER sync`). With `writer: not
  running`, write nothing (no folder, no file, no `summary set`), say so in one line, act as that
  line says (start the surface server, or, when it names an older board, ask the user to stop it),
  then archive. In-project mode has no writer and refuses nothing: write in
  `.agents/changes/5-archives/` like any other write there.
- Read the PR with the forge's CLI, read-only: GitHub `gh pr view <link> --json
  number,title,url,author,state,mergedAt,files,body`; GitLab `glab mr view <link>` and its changed
  files with `glab` as the installed version allows. You need the title, link, author, merge time,
  files changed and description.
- Write nothing, and say why in one line, when the PR is not merged (`state` is not `MERGED`, or no
  merge time); a CR of a batch's record names it (it is chantier's: `order merged` records it); an
  outside archive of its number already exists (`5-archives/*-outside-<number>-*`): name it.
- Write `5-archives/<YYMMDD-HHMM>-outside-<number>-<slug>/`, UTF-8 without a byte-order mark: the
  time is the merge time, UTC; the number is the forge's, digits only; the slug is the title as
  `file` makes one (lowercase letters and digits, other runs one hyphen, at most 40 characters).
  Two files: `intake/request.md`, the description as received (an empty one: the title alone as a
  `# ` heading line); and `delivery.md`:

  ```markdown
  # Delivery

  - PR: <the PR's link>
  - Author: <the author's login>
  - Merged: <the merge time, YYYY-MM-DDTHH:MM:SSZ, UTC>
  - Archive in the PR: no

  <what changed, in a few lines: the files changed, grouped, and what the PR does>
  ```
- Then `$CHANTIER summary lint <the folder>` and `$CHANTIER summary set <the folder> --title "<the
  PR's title>" --summary "<one line: what it changed, by whom>"`. The writer publishes it at its
  next cycle (`$CHANTIER sync now` to publish at once). When `summary set` is refused (exit 2: the
  writer stopped), the files stay in the working tree for the next writer: tell the user, and run
  it again once `writer:` is back.
- Reply in one line: `archived <link> at 5-archives/<name>/`.

Shared understanding: ask whether a CR is grilled enough only after a complete restatement of it,
in the user's language: what it changes, every decision taken (from `02-answers.md`), what is
still open. The complete restatement ends with one line on the critic, just before the closing
"grilled enough?" question: `critic: yes, <why>` or `critic: no, <why>`, in the user's language
(e.g. "critique : oui, elle touche le contrat des Drivers"). The user corrects it, and a
correction is an answer (record it at once). The question itself follows "Asking the user: a
series". The closing question keeps its options: the user asks
for or cancels the critic in the tool's free answer or as a correction ("specify, no critic"); that
word is an answer, recorded at once in `02-answers.md`. Never decide on your own that a CR is
grilled enough: you ask, and the user decides. When the user says the CR is grilled enough, the
critic's yes or no goes into `02-answers.md` with that answer (e.g. `Spec critic: yes, it touches
the Drivers' contract.`), so a later session knows whether it is due.

Size, at "grilled enough?": when the CR's folder is very big (above 10 MB), the restatement says so
and you add one question in the same series format: what to do with it at the end of the
implementation (for instance A. keep the retained prototype zipped in the PR's archive and the rest
in the planning folder only; B. keep everything in the planning folder only, nothing in the PR's
archive; C. drop the non-retained versions at `close`). The answer is recorded in `02-answers.md`
and the specification carries it. A folder that grows very big during the batch is not asked about
by the Driver: it names it in the PR's Known gaps ([driver](driver.md)), the ready line quotes it,
and you ask the user at the ready.

**The spec critic.** A fresh `spec-critic` ([`spec-critic.md`](spec-critic.md)) reads the request,
the answers, the specification and the repository, and looks for a gap with the request's intent,
an inconsistency with the rest of the software, an unproved claim about the real world, a bundle
(work that would ship more cheaply as separate CRs). It never
edits the specification. It runs once per specification, on a CR you judge impactful; it is never
a loop. A bundle finding is always a question for the user, the split recommended. On the user's
split: the parts split off are filed as new inbox items (`$CHANTIER file`, one per part, each with its
own short title, the raw request naming the CR they come from), the answer is recorded in `02-answers.md`, and the
spec-writer's next run narrows the specification to what stays. The Griller follows the same steps.

- **The criterion** (the same for the Chief of Staff and a Griller): the critic runs on a CR whose
  specification, if wrong, would cost the user most: it changes what a role does or may do (a
  card's contract, the CLI's refusals, a host behaviour), what the user sees or decides, an
  irreversible or shared step (merge, release, push, a tracker post), or several areas at once. It
  does not run on a CR that changes wording, a doc or a test alone with no behaviour behind it.
  The subject and the priority decide nothing by themselves. You judge, and say why in the critic
  line. An automatable CR with no specification gets no critic.
- **Items grilled before the critic existed** have no `Spec critic:` line in `02-answers.md`:
  whoever starts their spec-writer judges then, by the same criterion, says the critic line to the
  user in the same message as the start (the user may flip it), and records it in `02-answers.md`.
  A specification already final then gets no critic unless the user asks.
- **Its model:** Opus 5.5 by default, from `$CHANTIER playbook`. When the user asks for Fable, for
  one run you start the critic with `claude-fable-5-2` through the host's model parameter; for the
  project, the role's model is set in `chantier.yaml`. A host that does not offer Fable: say so to
  the user and run the default, never a look-alike model. The critic line names Fable when it is
  asked for (e.g. "critic: yes, on Fable, …").
- **The steps**, in this order, after the spec-writer ends:
  1. You review its specification against `02-answers.md` as above (nothing dropped, nothing
     invented).
  2. With the critic due, start one `spec-critic` in the background (you, or the Griller who
     grills), its first line copied unchanged from `$CHANTIER playbook` (`spec-critic prompt,
     first line: …`) or the Spec critic's row of "Starting an agent" in
     [concepts](concepts.md), with the agent and model the playbook prints for it; the prompt
     names the card and the CR folder and nothing of the grill. `work/specifying` stays the guard
     of the specification from the spec-writer's start until the specification is shown: each
     agent started on it (the critic, the spec-writer's next run) replaces its line with `<time>
     <agent id> <role>`; no other spec-writer or critic starts while it exists; remove it when the
     last of them ends. A refused first line or a host failure: restart once, as for a
     spec-writer. This marker is also what the `limits:` line counts, so a CR waits for its
     turn by the limit above, never by a marker you leave behind.
  3. Sort its findings. Each one that touches behaviour (scope, behaviour, risk: what the user
     would decide) becomes a question for the user; each other one (a record fix, a wrong name, a
     dropped decision, an old rule left standing, an inconsistency whose answer is already
     settled, an unproved claim to mark as unproved with its trial) is a fix. An unproved claim
     that a decision rests on is a question. Every finding takes one of the two ways.
  4. **The fixes first:** with any fix, run the spec-writer once with them in its brief, before
     the user sees anything of the critic. It applies each, or says why one does not hold; then
     review again against `02-answers.md`. A fix it refuses for a reason you accept is dropped;
     one you do not accept becomes a question.
  5. **Then the user**, in the text before the question tool: one summary line, in the user's
     language, counting what is true at that point (e.g. "critique : 10 points, 6 corrigés sans
     vous, 4 questions"; a dropped one is counted too, e.g. "1 écarté"); then the questions, in
     the format of "Asking the user: a series" (text first, `<short name>-Q<n>` references
     continuing the item's numbering, at most 5 per call), together with the specification's own
     open questions. With no question: the summary line, then the
     specification, the fixes already applied. With no finding: "critique : aucun point", then the
     specification. The full list is shown on request, from the critic's reply, while the session
     lasts: it is written nowhere.
  6. **The answers:** record them in `02-answers.md`, then a second spec-writer run folds them, as
     above; review again. Start the critic again only if those answers change behaviour (one more
     pass, the same steps; its summary line says so, e.g. "critique, 2e passage : …"). Otherwise
     the specification is final once the user approves it.

Ticket summary: a CR with an `issue:` line ([concepts](concepts.md)) has its ticket's reporter told
what was accepted, before any code. A CR with none skips the whole block; say so in one line only
when the user asked about the ticket. A reference built on this shape:
[ticket-summary-example](ticket-summary-example.md). Steps, in this order:

1. **When.** When the user says such a CR is grilled enough, in the same turn as the spec-writer's
   start. A Griller that ran the grill may have written the drafts already
   ([griller](griller.md)): offer them when you next read the CR's folder.
2. **Can chantier write to that tracker?** Decided before any draft, from what the session has:
   - GitHub: `gh`, already used by the session, reaching the issue (`gh issue view <link>`).
   - GitLab: `glab`, reaching the issue (`glab issue view <id>`).
   - Jira, and any other tracker: the access method is not fixed (an MCP server, a CLI or another
     tool). The project's rules say which, when they do. Otherwise look for the capability the
     session has (its MCP tools for that tracker, an installed CLI) and use the one found,
     provided it reads the ticket. This card names no Jira CLI and no MCP server.
   - No capability found, or no access: **skip** the step and tell the user in one line, naming
     what is missing (for example "no way to write to Jira found in this session (no MCP tool, no
     CLI): nothing drafted for <KEY>"). Nothing is drafted, nothing is posted.
3. **The project's rules first.** Read what `$CHANTIER rules` lists for any rule on tickets: the
   tracker, its access method and project key, the reference form and closing keyword (for
   instance "tickets in this project use `Closes JIRAJPT-1245`"), the comment's language, a
   comment template. Where a rule speaks, it is followed; the defaults of this block apply only
   where the project says nothing.
4. **Draft, in the CR's `work/` folder** (UTF-8, no BOM, written with the host's Write tool):
   - `work/issue-comment.md`, **the comment**: accepted or not; the scope in two to five bullets;
     what is left out; the line "No date yet; the pull request will be linked here." When the
     plan and the demo go as separate artifacts or attachments, one line links them (filled after
     they are posted, step 7). Written for the reporter: no CR number or slug, batch, round,
     agent role, cost, requirement ID or `.agents/changes/` path.
   - `work/issue-plan.md`, **the plan**: the grill's decisions rewritten for an outside reader:
     what changes for the user, the limits, safety, what the docs will say.
   - `work/issue-demo.html`, **the demo**, only when the change is visible and can be imitated
     without the product (judge, and say why in one line; no demo otherwise): one self-contained
     file, no external resource (no `http(s)` `src`, no `href` to a stylesheet, font or CDN), no
     script unless the imitation needs one, the product's real colours and wording. Its first
     line is an HTML comment saying it imitates the planned result and is not the product; the
     page's first visible line says the same. It is not the batch's "demo" (section "Subagents
     and the demo"), which runs the real code.
   - **Language:** the ticket's language (read from its title and body), English by default,
     whatever the chat's language; a project rule on it ranks above.
5. **Check before showing.** The ticket named in the draft is the one of the CR's `issue:` line
   (its title, read from the tracker, is shown with the ask); the three texts hold no private
   path (a home folder, a drive letter, `.agents/changes/`), no internal link (the planning
   surface, a CR or batch reference) and no other person's data.
6. **Show and ask, in one step.** The comment and the plan as text in the chat, the demo as a file
   (its absolute path, or the host's means to send a file when it has one); the route each part
   will take (step 7) and the tool that will post it; the ticket's link and title; and, for each
   project rule followed, the rule quoted ("Followed: `<the rule's text>`, from `<file>`"). Ask
   for a yes **for that ticket**. The user may edit any part, drop the demo (or the plan), or
   decline. Record the answer at once in the CR's `02-answers.md` (yes, edits, drop or no), with
   the date and the user's words. No yes, nothing is posted; a "no" ends the step for that CR.
7. **Publish, on the yes only, by the Chief of Staff only.** Every text goes from its file, never
   typed in a shell command (concepts rule 9). The route for the plan and the demo is chosen
   before the ask (step 6) from what the tracker and the capability offer, in this order: the
   tracker's issue artifacts, else its attachments, else a collapsed section (`<details>`) of the
   comment. Per tracker:
   - **GitHub** (unproved; trial: the eval `ticket-summary`): when `gh issue artifact --help`
     lists `create` (it does in gh 2.103.3, in preview, so its flags may change: read the help
     again), the artifacts: `gh issue artifact create <link> work/issue-plan.md --type plan`,
     then `gh issue artifact create <link> work/issue-demo.html --type embedded_html`; read them
     back with `gh issue artifact list <link> --json number,name,url`; put their links in the
     comment's link line (Edit), then `gh issue comment <link> --body-file work/issue-comment.md`.
     With a `gh` without `gh issue artifact`: collapsed sections of the comment (the plan as
     Markdown; the demo as a fenced `html` block). GitHub's comment `--attach` takes only images
     and video, so there is no attachment tier on GitHub.
   - **GitLab** (unproved; trial: a note posted from a file holding backticks, `$` and quotes,
     matching the file on the tracker): `glab issue note` with `glab`'s option that reads the
     message from a file. The plan and the demo as uploads when the installed `glab` offers a
     command that uploads a file to the issue's project (read its help), else collapsed sections
     of the note.
   - **Jira and other trackers** (unproved; same trial): the capability found in step 2 (MCP
     tool, CLI or other): its comment action, taking the text from the file (for a CLI, its file
     option; for an MCP tool, the file's content passed as is, never retyped), and its
     attachment action for the plan and the demo when it has one (read its help or its tool
     description). With no attachment action: a collapsed section where the tracker's markup has
     one; else the plan goes in the comment's text and the demo is left out of the post, said to
     the user in the ask.

   A refused or failed post is told to the user with its exact text and stops the step: the
   texts stay in `work/`, nothing is retried another way and no lower route is tried after a
   failure (concepts rule 2). When an artifact or attachment fails, the comment is not posted.
8. **Verify after publishing.** Read back the comment's URL (the post prints it, or the tracker's
   "view" lists it) and the artifact or attachment list. Tell the user, in a few lines, what is
   visible and to whom: for instance GitHub issue artifacts are a preview feature and may be
   hidden from the reporter.
9. **Record** in the CR's `02-answers.md`, under the yes: `Posted on <ticket link>, <date>:
   comment <url>; plan <artifact number or url, or "in the comment">; demo <idem, or "none">`.

**PR follow-up.** The first time you see the PR link of a CR with an `issue:` line and a recorded
post (a `status`, a hand-back, an ask, a report), propose a one-line comment for that ticket, in
the ticket's language: "The pull request is open: <PR link>." Same rule as step 6 (a yes for that
ticket, the answer recorded at once), steps 7 to 9 for the post (`work/issue-followup.md`). A CR
whose summary was declined or skipped gets no follow-up proposal. In a series or a stack the PR
opens as a draft: the follow-up is still proposed then. "Released in" (`chief-of-staff:release`) is the
closing comment of the request's "Land" row, unchanged.

Triage each CR with the user, who decides its way: dropped (`abandon`); **automatable**, with a
short specification they do not review; needing a specification they review until they approve
it; or needing clarification: grill, then triage again. Automatable is their call, never yours:
such a CR may go to `3-ready` with no specification, and its Driver works from the request alone.
