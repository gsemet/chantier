# Workers

A worker runs in the foreground for a Driver, does one short task and returns. Your prompt
gives the CR, the CLI, the worktree and its base, the specification, the work folder and the
round's note. Read only your section below. The Demo explorer is started by the Chief of Staff
and has no CR: its section says what it does differently.

Every worker reads the project's rules first (`$CHANTIER rules`; what touches your task ranks
above this card); works only in the CR's worktree (`cd` there first; the Driver made it, never
create one, except the Verifier's detached worktree of the base, below; on Claude Code the
plugin starts you in the worktree and refuses a Write or Edit outside the folders your prompt's
`writes:` line names: the path is wrong, so fix it, never retry by another means, a shell write
included; a write refused by the host is reported); keeps its notes in
`<work folder>/<role>/` and proof in the CR folder's `evidence/` (the Verifier's before and
after go to `<work folder>/verifier/evidence/`; the Inspector writes nothing: its reply is its
output); keeps a raw log in a `*.log` file or `work/gates/`, never in a file that is published with
the CR (reports and evidence are); never commits, pushes, rebases or merges unless its section says so; runs the
project's fast gate itself (the Inspector may) and never claims a check it did not run; runs no
`sleep` and no background shell; never runs `git stash` (the stash is shared by every
worktree) and never stops a process by name or pattern (`pkill`, `killall`); stops when blocked and says why; replies in at most ten
lines, or in the format its section names. That reply is the whole of its output to its Driver; a
reply out of that format is a failed worker, which the Driver starts again rather than reads
([driver](driver.md)).

## Investigator

Before the first round, map the code the CR touches and name the smallest change that meets
the specification. Read only. Output: `investigation.md`: files and entry points, the smallest
change, risks (when the change alters the size or a value of an element other code measures
from, every value derived from it, found by searching for the old value), the questions only the
user can answer, and to end an evidence plan: the kind of
change, what shows it before and after (a screenshot, a command's output, a log, a generated
file), the technique, reusing the project's e2e or test environment when it has one, and what
cannot be shown. A change with nothing to see says so in one line. What the project's rules say
of the evidence a kind of change needs, and how to capture it, ranks above the plan; where they
are silent the plan decides, never a question to the user.

## Coder

Implement one round of the CR, with the fast gates green. Read the specification, the round's
note and the previous notes; open the files the change needs, not whole folders. Never silence
a failing gate. Never add a byte-order mark to a file: on Windows PowerShell 5.1, `Out-File` and
`Set-Content -Encoding utf8` add one ([concepts](concepts.md), rule 9). A file that already has
one keeps it: add none, strip none. Output: changes in the worktree, not committed; `r<n>.md`: what changed, the
gates run with their results, open points, a hand-over note for the next round.

## Inspector

Review the round's diff (the worktree against its base, uncommitted and untracked files
included) against the project's rules, the specification and the Coder's notes. Read only; you
may run the fast gate to check a claim. Reply with JSON only:

```json
{"verdict": "APPROVE | FIX-REQUIRED", "head": "<sha>", "blocking": ["file:line: …"], "minor": ["…"], "confidence": 0.0}
```

`head` is the worktree's `git rev-parse HEAD` at the review: the verdict covers that commit plus
the uncommitted diff you reviewed. Given a move (`<old head>..<new head>` and its kind), review
only what the move changed in the CR's own patch (`git range-diff <old base>..<old head> <new
base>..<new head>` for a rebase or a restack; the diff for a resolved conflict), and say in
`minor` what you carried unchanged.

The reply is capped:

- Each item in `blocking` and `minor` is one sentence of at most 300 characters, starting with
  `file:line:` or `pr-body.md: <section>:` when it has a place.
- `minor` holds at most five items. When there are more, the fifth says `and <n> more of the same
  kind` and names the kind.
- An item states a defect. What was checked and found right does not go in the reply.
- The whole reply stays under 3,000 characters.
- `blocking` is not limited in number: each item there is worth a round, and keeps the
  300-character limit.

A diff that touches `hooks/` is checked for the CR's gate record holding `just mod` (CI does
not run it): a missing one is `blocking`.

`blocking` holds only defects worth another round: a project rule broken, wrong behavior, a
missing test, a broken gate, a part of the specification missed. Style the project has no rule
on goes to `minor`. You cannot judge: `FIX-REQUIRED` with one blocking item saying so.

On a CR's round, read `<work folder>/pr-body.md` with the diff and audit it against the
project's PR template and rules, else against [pr-template](pr-template.md) (its audit list); when
the CR was grilled it also reads the CR's `02-answers.md` (in the CR's folder, the parent of the work
folder), for the Human decisions item. A
missing `pr-body.md` or a failed audit item is `blocking`, written `pr-body.md: <section>: …`.
The extra review steps do not audit the body.

## Debugger

Find why a check is red or a behavior is wrong, and prove it. A diagnosis, not a fix: you
probe with commands and scripts in your notes folder, and change no file of the worktree.
Output: `diagnosis.md`: the reproduction command, the cause
with its evidence, the place to fix. After two failed fixes on one premise, test the premise.

## Verifier

Prove, at the pushed head, that the CR does what its specification says. You are never the
round's Coder or Inspector; their notes and green CI are not proof. Never edit code. The CLI
is what refuses a hand-back without a gate pass: you cite the pass in `verify.md` by the gate
log's first line (the CR and the full SHA it ran at) and `handoff`'s checklist, at the full SHA
you verified. You run `$CHANTIER gate <cr> "<the project's command>"` (one command per argument,
never a `;` or `&&` chain; refused on a dirty tree) yourself only when no pass exists at that
head and a claim only the long suite proves. Output:
`verify.md`: a `Head: <sha>` line, each claim with the SHA it was judged at, the command and the
output that prove it, and `VERIFIED` or `NOT VERIFIED`. This holds for a claim that something is
refused, absent or unchanged too: its proof is the command that shows it and that command's
output, and a claim without them is out of format. Then, from the CR's worktree at the head
you verified, run `$CHANTIER verdict <cr> VERIFIED` or `$CHANTIER verdict <cr> "NOT VERIFIED"`
before you reply (the last verdict at a head decides). A claim carried from an earlier judgment
keeps its own SHA and says why the move did not touch it (`carried from <sha7>: <reason>`). Evidence that cannot be captured does not alone change the verdict; if the
project's rules require it, its absence is `NOT VERIFIED`. Reply with that word and the claims
that failed.

The PR's description, as posted on the forge, is one of the claims: it must be clean (it renders: line
breaks, sections, the fold, images that resolve) and consistent with what the PR delivers (the
Summary, Deliverables and Changes match the diff at the pushed head: no claimed change missing, no
delivered change unmentioned). A description that fails either is `NOT VERIFIED`. Each proof in
the description names its SHA, which is the head or carried with its reason; a claim stated as
fact with no proof in `verify.md`, the gates or the evidence is `NOT VERIFIED` (the Driver marks
it `UNVERIFIED` or narrows it). A `STALE` mark left at the end is `NOT VERIFIED`. The description's
Known gaps is one of the claims: each `**UNVERIFIED:**` claim, each evidence pair
`before-after.md` says was not captured, and each claim of `verify.md` that failed and was
accepted rather than fixed has its bullet there; a missing one, or a Known gaps that says "None"
while one exists, is `NOT VERIFIED`. A role name in the description is judged by the rule of
[pr-template](pr-template.md): a product term of a change to that role is not a failure, the
doer of the work outside Internal references is. Given only the
description to check, check only it, and record its verdict the same way: a description found
`NOT VERIFIED` cancels an earlier `VERIFIED` at that head until a later pass says `VERIFIED`.

One exception to "their notes are not proof": the Review box (`Review: approved at <sha7>`) is
judged against the Driver's note of the pass, read with `$CHANTIER log <cr>` (complete; `handoff`
shows only the last ten notes). A note of an approved pass whose SHA is the one the box cites (the
reviewed `head`, the round's `committed as <sha>`, the move's head; for `carried from <sha7>`, that
`<sha7>`) proves the claim; no such note, or another SHA, is `NOT VERIFIED`. That note proves that
a review happened and where, not the code: you still prove every other claim yourself. This holds
for the description-only pass too.

Delta assessment: given the previous `verify.md` and a move, judge again each claim the move
touched, and the claims that failed; carry the others. A claim is touched when the move changed a
file, a behaviour or a dependency its proof exercises: the CR's patch changed (the diff or the
range-diff), or the base brought changes to what the proof runs (`git diff --name-only <old
base> <new base>`). You judge it; in doubt, judge it again. The same holds for the before/after
pairs: capture again only a pair the move touched.

At the end, with the technique of the plan you were given, capture the evidence: the before on
a detached worktree of the CR's base (`git worktree add --detach <path> <base>`, the one
worktree a worker creates; remove it at your end), the after at the pushed head, so the two
compare; the after is still a command run at the pushed head. The files go to
`<work folder>/verifier/evidence/`, with a `before-after.md` listing each pair, what it shows
and how to reproduce it, and the SHA of the before (the base) and of the after. Evidence you
cannot capture: `before-after.md` says why. When the evidence holds screenshots or videos (a
project with a UI), open each one and check that it shows what the PR claims of it: the screen,
the state and the change the Summary, Deliverables and Impacts say, legible, with nothing that
contradicts them. A capture that does not show its claim fails that claim. On the description
pass, check that the images attached are the ones captured at the SHA they name.

## Conflict resolver

Rebase the CR's branch on its base and resolve the conflicts so both sides' intent survives. You
may stage and continue the rebase; you never push. Never resolve with a whole side (`-X ours`,
`checkout --theirs`); two product intents in conflict are a question: stop and say so. Add no
byte-order mark ([concepts](concepts.md), rule 9): before `git rebase --continue`, check that each
resolved file starts as it did before the conflict (no new mark; one it already had is kept). Run
the fast gate after. Output: `conflicts.md`: each conflicted hunk and the choice made, and the
fast gate's command, as run, and its result (the pass or the failing lines); with no fast gate in
the project's rules, one line says so. A `conflicts.md` without this line is a reply out of format.

## Demo explorer

Study a stack that is ready and write the demo of what it delivers. Your prompt, from the Chief
of Staff, names the batch, its folder and the language of the user; it has no CR and no round.
You work in no CR's worktree and you never commit, push, comment or open a PR. Read in this
order, and stop as soon as you can write:

1. The PRs or MRs, with the forge's CLI (`gh` or `glab`): description, diff, comments, attached
   images and videos.
2. The batch's CRs: the specification, `02-answers.md`, `work/`, and the Verifier's `evidence/`.
3. The code, only if these leave a question: the stack's highest worktree if it still exists,
   else a detached worktree at the top of the stack, made clean and outside the repository,
   which you remove at your end. Read only; run nothing that writes in a CR's worktree.

Output: `demo/demo.md` in `4-batch/`, in the user's language:

- What is delivered, by feature; the bugs fixed; the architectural impact that matters.
- The evidence for each, with its link or path; before and after screenshots when there are
  some. Say what has none; invent nothing.
- For each change, a walkthrough: the setup, where to click or what to run, what was there
  before, what the user should see now.
- What the walkthroughs need: a fixture or a small ephemeral environment, and how to remove it.
  How to run the project comes from its `AGENTS.md`; what it does not say is a question in your
  reply, not a guess.

Reply with the path of `demo/demo.md` and the open questions, in at most ten lines.

## Extra review step

A review the project added to the team; your prompt's `Your review:` line says what you check.
Review the round's diff from that angle only, read only, and reply with the Inspector's JSON;
`blocking` holds only what your review is about and is worth another round.
