# PR template

The default description of a CR's PR, written by the CR Driver and checked by the Inspector.

## Scope and precedence

- It is the description of a CR's PR (GitHub) or MR (GitLab), written in `<work folder>/pr-body.md`. A fix CR follows it too; a stack driver opens no PR; a release PR keeps its form.
- The project ranks above it: a template file the forge reads (GitHub `pull_request_template.md` in the root, `docs/` or `.github/`, or `.github/PULL_REQUEST_TEMPLATE/`; GitLab `.gitlab/merge_request_templates/`, `Default.md` when several), or a template or PR rule from `$CHANTIER rules`. Then that template is used as written and this file fills only where it is silent; the Issues References lines go where it puts issue links, else in a `## Issues References` section after its first section.

## The rules

- English, for a reader outside the team who does not know the backlog; `.agents/changes/` is not in git. Explain from the reader's side: what was wrong or missing, what changes, what they will notice. Name features by what they do; define a project term on first use.
- `archive: in the PR at <path>`: the archive folder is part of the diff, named only in Internal references; the check of the description against the diff takes it as expected. `archive: not in the PR`: the description names none.
- No internal reference in the title or the body text: no CR name, number or slug, no batch, round or order, no `.agents/changes/` path, no chantier role (Chief of Staff, Foreman, Griller, Driver, Coder, Inspector, Verifier, Investigator, Debugger, Conflict resolver, Spec-writer, Spec critic, Demo explorer) as the one who did the work. The CR's name ("CR-<n> <slug>") goes in the last section, "Internal references", and nowhere else.
- A role name may appear anywhere when it is a term of the project's own product (the diff changes that role's behaviour, card or agent file), defined on first use. A path the diff changes may be named in Changes.
- With an `issue:` line in the specification, the body has `## Issues References`, one line per ticket, in the form the project's rules give, else: Jira `Closes <KEY>-<n>`; GitHub and GitLab `Closes #<n>` (another repository `Closes owner/repo#<n>` or `Closes group/project#<n>`); any other tracker, the ticket's link. The verb closes the issue at merge; a project that wants a link only says so. This is the only place the PR names the ticket, and the Driver never comments on the issue. With no `issue:` line, no section.
- The title says what changes; with no project style, a Conventional Commit subject (`feat: …`, `fix: …`).
- Every section is kept and filled, "None" rather than deleted. Human decisions is the exception: omitted when the CR had no grill (a quick fix, a fix CR) or its answers hold no decision that shapes the change.
- Layout: Summary, Issues References (when present), Deliverables, Blast radius, Autonomous decisions and Known gaps are visible, in that order; the rest is in one `<details><summary>Details</summary>` block: Changes, Human decisions, Impacts, Test plan, Internal references. A blank line after `</summary>` and before `</details>`; nothing after `</details>`. Before/after screenshots stay in Deliverables.
- Deliverables, right after Summary: what the reader gets, as one or more small visuals each next to the sentence it supports, and the impactful choices made (UI: aesthetic and behaviour; architecture: the choices; refactoring: the targets). A visual is one of: a Mermaid `flowchart` of the modules that change (about 10 nodes); a `sequenceDiagram` of one real flow; a before/after tree or table; before/after screenshots of a visible change, side by side, attached with the forge's own CLI (a link into a commit of the branch is no upload: a restack drops it); a 5 to 15 line code sketch of the new interface. Only what the reviewer needs, with real names checked against the diff. A one-line fix may write "None"; a structural change never does.
- Impacts: what users and developers will notice; one line on what the screenshots show. A file the forge's CLI cannot upload is named in Internal references. Nothing visible: "No visual change".
- Each proof names its SHA (seven characters): the Test plan items and the screenshot captions (before at the base's SHA, after at the head's). A clean rebase carries every proof whose patch it left unchanged; a carried proof reads `at <head7> (carried from <sha7>)`; a proof the head has moved past is `STALE (judged at <sha7>, head now <sha7>)`. A claim with no proof starts with `**UNVERIFIED:**` or is narrowed to what is proven. The Review item cites the SHA of a pass recorded with `$CHANTIER note`, and stays unchecked while none is.
- Human decisions: the decisions the user took in the grill that shape the change, from `02-answers.md` (in the CR's folder), one bullet each, no internal reference.
- Blast radius: one grade, explained in one or two lines (what could break, how to roll back).
- Autonomous decisions: each decision an agent took without the user, one bullet with its reason; "None" when none.
- Known gaps: each gap the PR leaves on purpose, one bullet with what is missing and why (and what would close it): a part of the specification not delivered, each `**UNVERIFIED:**` claim, evidence the Verifier could not capture, a defect accepted rather than fixed, a cosmetic one included. A `STALE` proof is never a gap: it is fixed first. "None" when none; never deleted; no internal reference.
- The body describes the PR as it is now, not its history: update it whenever the scope changes.

## The template

To copy into `pr-body.md`:

```markdown
<!-- Title and body in English, for a reader outside the team: no internal ids (CR, batch,
round, .agents/changes/ paths), no agent role as the doer of the work; a role name only as a
product term of a change to that role. Put such references, the CR's name first, in the
last section "Internal references". Fill every section; write "None" rather than delete one,
except Human decisions, omitted when the CR has no decision from the grill to show, and Issues
References, omitted when the CR has no source ticket. Keep the fold
as written. Name the SHA of each proof; mark a stale one STALE and an unproven claim
UNVERIFIED. -->

## Summary

<!-- Why: the user problem or limitation this solves, in two or three sentences. -->

## Issues References

<!-- One line per source ticket, in the form the project's rules give, else: Jira
`Closes <KEY>-<n>`; GitHub and GitLab `Closes #<n>` (another repository:
`Closes owner/repo#<n>`, `Closes group/project#<n>`). Delete this section when the CR has no
source ticket; never write "None". -->

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

## Known gaps

<!-- Each thing this PR leaves on purpose: not done, not proven, or a known defect accepted,
one bullet with why; every UNVERIFIED claim has its bullet. Or "None". -->

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
- [ ] Review: approved at `<sha7>` <!-- the SHA of the pass recorded in the CR's notes; unchecked until it is -->
- [ ] Verified at `<sha7>` <!-- a claim carried from an earlier SHA reads `at <head7> (carried from <sha7>)` -->
- [ ] CI green at `<sha7>` <!-- or, checked, "No CI: no check listed at <sha7>" when the forge lists no check at the head after two looks; never deleted, never "CI green" then -->

## Internal references

<!-- Always last: the CR's name (number and slug, e.g. "CR-<n> <slug>"), work files,
anything only the maintainers need. -->

</details>
```

## The audit

What the Inspector checks, one line each, so a defect names its section:

1. Every section of the template present (Known gaps included), in order, each filled or "None"; Human decisions present only when `02-answers.md` records a decision that shapes the change; Issues References present only when the specification has an `issue:` line; Internal references last.
2. The fold in place: one `<details><summary>Details</summary>` block after Autonomous decisions, holding Changes, Human decisions (when present), Impacts, Test plan and Internal references, a blank line after `</summary>` and before `</details>`, nothing after it; the other sections outside it; the screenshots in Deliverables.
3. No internal reference, the CR's name included, in the title or outside Internal references (Human decisions included); no role name as the doer of the work; a role name elsewhere only as a product term of a change to that role.
4. Deliverables has at least one visual unless the change is a one-line fix; its names exist in the diff or the code; it shows the impactful choices.
5. Changes and Impacts match the diff and the specification: nothing claimed that the diff does not do, nothing the diff does left out.
6. Blast radius has one grade and its explanation.
7. Autonomous decisions lists the decisions the round's notes record as taken without the user, or says "None".
8. Human decisions matches `02-answers.md`: each decision that shapes the change is there, nothing dropped, nothing invented.
9. With an `issue:` line, Issues References holds one line per ticket in the form the rules give, and the body names the ticket nowhere else; without one, no section.
10. Known gaps present, visible, right after Autonomous decisions; one bullet per `**UNVERIFIED:**` claim and per gap the notes record as left; "None" only when none.

With a project template, the audit is that template's sections, filled as it asks, and the project's PR rules.

## A customised version

On the user's request the Chief of Staff files it as a CR (`$CHANTIER file`), grilled and specified like any CR; a CR Driver delivers it by PR. The CR writes a guideline (the rules) and a template in the user's project, starting from this file and the user's wishes, at the place the agent judges right unless the user's answers name one, and links the guideline from the project's instruction file so `$CHANTIER rules` lists it. Once merged, the project's version ranks above this file.
