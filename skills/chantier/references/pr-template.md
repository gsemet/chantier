# PR template

The default description of a CR's PR, written by the CR Driver and checked by the Inspector.

## Scope and precedence

- It is the description of a CR's PR, on GitHub and on GitLab (merge request), written by the CR
  Driver in `<work folder>/pr-body.md` and checked by the Inspector. A fix CR is a CR: its PR
  follows it too. A stack driver opens no PR; a release PR keeps its form.
- The project ranks above it: a template file the forge reads (GitHub: `pull_request_template.md`
  in the root, `docs/` or `.github/`, any case, or a template in `.github/PULL_REQUEST_TEMPLATE/`;
  GitLab: `.gitlab/merge_request_templates/`, `Default.md` when there are several and the rules
  name none), or a template or PR rule that the project's rules (`$CHANTIER rules`) give. Then
  the project's template is used as written, and this file only fills where the project is
  silent.

## The rules

- Title and body in English, for a reader outside the team: reviewers, stakeholders, future
  maintainers. They do not know the backlog, and `.agents/changes/` is not in git (but see the
  archive below).
- When `take` says `archive: in the PR at <path>`, that archive folder is part of the diff: the
  description names it only in its Internal references section, as any `.agents/changes/` path,
  and the Verifier's check of the description against the diff takes it as expected, not as an
  unexplained file.
- Explain the change from the reader's side: what was wrong or missing, what the PR changes, what
  they will notice. Name features by what they do, not by internal ids. Define a project term on
  first use.
- No internal reference in the title or the body text: no CR name, number or slug, no batch,
  round or order, no agent role (Driver, Coder, Inspector…), no path under `.agents/changes/`.
  The CR's name ("CR-142 grill-rules") and any other reference that helps maintainers go in the
  last section, "Internal references", and nowhere else.
- The title says what changes; where the project's rules give no style, a Conventional Commit
  subject (`feat: …`, `fix: …`).
- Every section is kept and filled; "None" rather than a deleted section. One exception: Human
  decisions is omitted, never written "None", when the CR has no decision to show: it had no grill
  (for instance a quick fix, or a fix CR, whose specification is a `fix-<n>.md` and which has no
  `02-answers.md`), or it was grilled but its answers hold no decision that shapes the change.
- The layout: Summary, Deliverables, Blast radius and Autonomous decisions are visible, in that
  order; the rest goes in one `<details><summary>Details</summary>` block, in this order: Changes,
  Human decisions, Impacts, Test plan, Internal references. A blank line after `</summary>` and
  before `</details>`, or the forge does not render the Markdown inside; nothing follows
  `</details>`. The before/after screenshots of a visible change stay in Deliverables, outside the
  fold.
- Deliverables, right after Summary: what the reader gets, shown with one or more small visuals,
  each next to the one or two sentences it supports, and the impactful choices the change made, by
  kind of change: for a UI, the important aesthetic and behaviour choices; for an architecture, the
  architecture choices; for a rework or refactoring, the targets set (for instance scores to
  reach). The visuals are one kind, sometimes several, rarely all:
  - a Mermaid `flowchart` of the modules or layers that change, arrows for the calls or allowed
    imports (about 10 nodes at most);
  - a Mermaid `sequenceDiagram` of one real flow, before and after when the order is the fix;
  - a before/after tree or table (files moved or split, sizes, settings);
  - before/after screenshots for a visible change, its main visual, side by side, attached as
    [driver](driver.md) says (the forge's own CLI);
  - a 5 to 15 line code sketch of the new interface, message or registration a contributor will
    reuse, with `...` for the rest.

  Only the calls, files, props and boundaries the reviewer needs, with real names checked against
  the diff. A one-line fix may write "None"; a structural change never does.
- Impacts, inside the fold: what users and developers will notice. The Verifier's before/after
  screenshots are in Deliverables, not here; Impacts says in one line what they show. A file the
  forge's CLI cannot upload is named under "Internal references" (its path is under `work/`),
  not in the text. With nothing visible: one line, e.g. "No visual change".
- Each proof names the SHA it covers (seven characters): the Test plan items, and the captions of
  the before/after visuals in Deliverables (before at the base's SHA, after at the head's). A
  proof carried over a move says so (`carried from <sha7>`). A proof the head has moved past, not
  yet judged again, is marked `STALE (judged at <sha7>, head now <sha7>)`. A claim in Summary,
  Deliverables, Changes or Impacts with no proof (no test, no gate, no Verifier claim, no
  evidence) starts with `**UNVERIFIED:**`, or is narrowed to what is proven; it is never left as a
  plain fact.
- Human decisions, inside the fold: the impactful decisions the user took during the grill,
  extracted from the CR's `02-answers.md` (in the CR's folder, the parent of the work folder):
  only the decisions that shape the change, not every answer; one bullet each. No internal
  reference (no CR, batch, round, agent role, `.agents/changes/` path), written for a reader
  outside the team. Omitted when there is no such decision (no grill, or a grill with none).
- Blast radius: one grade kept, explained in one or two lines (what could break, how to roll
  back).
- Autonomous decisions, visible right after Blast radius: each decision an agent took without the
  user (in the investigation, a round, a conflict resolution), one bullet each, with its reason;
  "None" when there is none.
- The body describes the PR as it is now, not its history: it is updated whenever the scope
  changes (a new round, a dropped item, a rebase that changes what the PR holds).

## The template

To copy into `pr-body.md`:

```markdown
<!-- Title and body in English, for a reader outside the team: no internal ids (CR, batch,
round, agent roles, .agents/changes/ paths). Put such references, the CR's name first, in the
last section "Internal references". Fill every section; write "None" rather than delete one,
except Human decisions, omitted when the CR has no decision from the grill to show. Keep the fold
as written. Name the SHA of each proof; mark a stale one STALE and an unproven claim
UNVERIFIED. -->

## Summary

<!-- Why: the user problem or limitation this solves, in two or three sentences. -->

## Deliverables

<!-- What the reader gets, with small visuals each next to the sentence it supports: a Mermaid
flowchart of the modules or calls that change (about 10 nodes), a sequence diagram of one real
flow (before and after when the order is the fix), a before/after tree or table, or a 5-15 line
code sketch of the new interface. For a visible change, the before/after screenshots side by
side are the main visual. Also the impactful choices made, by kind of change: UI, the aesthetic
and behaviour choices; architecture, the architecture choices; rework or refactoring, the targets
set. Real names, checked against the diff. A one-line fix may write "None"; a structural change
never does. -->

## Blast radius

<!-- Keep one grade and explain it in one or two lines: what could break, how to roll back. -->

- **1**: local and isolated; a plain `git revert` restores the previous behaviour.
- **2**: several features or shared code; revert is possible but needs checks or follow-ups.
- **3**: wide impact (data, formats, CI, release, public API); rollback is complex or partial.

Grade: <!-- 1 | 2 | 3 -->

## Autonomous decisions

<!-- Each decision taken without the user, one bullet with its reason; or "None". -->

<details>
<summary>Details</summary>

## Changes

<!-- What: the key mechanisms and files, as a short list. Not a diff summary. -->

## Human decisions

<!-- The decisions the user took during the grill that shape the change, from the CR's
02-answers.md, one bullet each, no internal reference. Delete this section when there is none
(no grill, or no decision that shapes the change); never write "None". -->

## Impacts

<!-- What users and developers will notice. The before/after screenshots are in Deliverables:
say here in one line what they show. With nothing visible, one line, e.g. "No visual change". -->

## Test plan

- [ ] New or changed tests (they fail on the previous code) <!-- or "No behaviour change" -->
- [ ] Local gates at `<sha7>`: <!-- the commands run and their results -->
- [ ] Evidence: before at `<sha7>`, after at `<sha7>` <!-- or why there is none -->
- [ ] Review: approved at `<sha7>`
- [ ] Verified at `<sha7>` <!-- claims carried from an earlier SHA say so -->
- [ ] CI green at `<sha7>`

## Internal references

<!-- Always last: the CR's name (number and slug, e.g. "CR-142 grill-rules"), work files,
anything only the maintainers need. -->

</details>
```

The studio's Test plan item on requirements (SwRS, `just requirements-update`) is specific to
that project and is left out; an Evidence item replaces it, as chantier's Verifier produces the
before/after.

## The audit

What the Inspector checks, one line each, so a defect names its section:

1. Every section of the template present, in order, each filled or "None", except Human
   decisions, present when the CR's `02-answers.md` records a decision that shapes the change and
   absent otherwise; Internal references last.
2. The fold in place: one `<details><summary>Details</summary>` block, after Autonomous
   decisions, holding Changes, Human decisions (when present), Impacts, Test plan and Internal
   references, with a blank line after `</summary>` and before `</details>`, nothing after it;
   Summary, Deliverables, Blast radius and Autonomous decisions outside it; the before/after
   screenshots of a visible change in Deliverables.
3. No internal reference, the CR's name included, in the title or outside Internal references
   (Human decisions included).
4. Deliverables has at least one visual, unless the change is a one-line fix; the names in it
   exist in the diff or the code; it shows the impactful choices the change made.
5. Changes and Impacts match the diff and the specification (nothing claimed that the diff does
   not do, nothing the diff does left out).
6. Blast radius has one grade and its explanation.
7. Autonomous decisions lists the decisions the round's notes record as taken without the user,
   or says "None".
8. Human decisions matches the CR's `02-answers.md`: each decision that shapes the change is
   there, nothing dropped, nothing invented; absent only when there is no such decision.

With a project template, the audit is: that template's sections, filled as it asks, and the
project's PR rules.

## A customised version

When the user asks for their own version, the Chief of Staff files it as a CR (`$CHANTIER
file`), grilled and specified like any CR; a CR Driver delivers it by PR. The CR writes a
guideline (the rules) and a template in the user's project, starting from this file and the
user's wishes, at the place the agent judges right unless the user's answers name one (for
instance the forge's template file, and a guideline next to the project's other rules), and
links the guideline from the project's instruction file so `$CHANTIER rules` lists it: what
`rules` does not reach, a Driver does not read. Once merged, the project's version ranks above
this file.
