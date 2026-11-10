# Life of a change request

Every change request, from Jira, a GitLab or GitHub issue, the chat, a Markdown file or a finding, is filed by the chantier CLI and lands in one Markdown file, 01-intent.md, in 1-inbox. A CR is usually implemented in a pull or merge request (PR/MR). Some CRs do not translate to a PR. The Chief of Staff, or a Griller (optional, another session of yours), triages it with you: drop it to 6-trash, send it straight to the backlog when it is automatable with a short spec, start the spec-writer agent, which the Chief of Staff or a Griller starts, in the background, on your word that the CR is grilled enough, to write a Change Specification you review until approved, or grill you (a Griller may too) and record your answers in 02-answers.md before triaging again. A prototype may feed your review: the destination, shown, such as a UI mockup or a vibe-coded app, often made by you, outside this cycle. In 2-backlog you set its priority, P1 to P4. The chantier triage command moves a CR to the backlog; chantier triage --ready moves it to 3-ready, where it waits for the next batch. On your go, the Chief of Staff opens a batch in 4-batch with chantier open, which queues the CRs in 1-pending; the steering session, the Foreman, or the Chief of Staff itself in direct mode (chantier open --direct), whose heartbeat loop runs chantier status --refresh, queues the CR and hands it with chantier take to a CR driver, runs it in its own worktree and branch: when the code is unfamiliar, an Investigator maps it before round 1; then rounds of Coder and Inspector until the driver approves the implementation, at most three rounds. Then a rebase, the gate and ship open the PR, so the gate passes on the final head; CI and a Verifier at the pushed head follow, and a red check or a failed verification is a new round. chantier take moves each CR to 2-actives. The driver hands back ready, you merge, and chantier order merged moves the CR to 3-done. With a stacked batch, a Stack driver orders, restacks and ships the PRs, runs the heavy CI once at the top and hands each CR back ready. On your request, at any time of the batch, the Foreman starts a QA driver that uses the head of the default branch as its user would, never an unmerged PR; its findings come back to the intake. The batch has three parts, all started by the Foreman: quality assurance, implementation and release. Once every other CR is merged or cancelled, the Foreman hands the release CR to a Release driver with chantier take; it runs your release procedure and its checks, and asks the Foreman before merging the release PR, which chantier release go allows on your approval or grant. A failed step writes fix-n.md, which becomes a fix CR on your go, unless your grant covers it; the fast track takes up to three fixes per release. A CR driver makes the targeted fix. A fix merges on its own only under your fix grant, an exceptional authorisation for this release's fixes, always bounded by a budget: the Foreman merges it within the granted budget; otherwise you merge it. Either way, the Release driver resumes to finish the release. Once released, the Release driver may monitor the deploys, on package registries, pages and the like, writes retro.md, whose recommendations come back to the intake as a process-improvement CR, and hands back ready; the release CR goes to 3-done. Once every CR is merged or cancelled, the Foreman runs chantier pause: the batch is paused, and its STATUS.md becomes the exit report, with the cost to date; the Foreman sends it as final to the Chief of Staff, who shows you the report and the cost. The batch stays paused and takes new CRs: new work sets it running again, and it pauses again at the end. Only on your later word ("close the batch") and your yes does the Chief of Staff run chantier close, the check, then chantier close --yes, which moves each CR of 3-done to 5-archives and deletes the batch's own files. The batch itself, running, paused, closed, is drawn in batch-lifecycle.svg. A blocked driver hands back to the Foreman, which may raise the question to the Chief of Staff, who asks you and sends orders back. A bug found outside the CR's scope goes to the Foreman too, which judges: the driver takes it into the CR, the Foreman raises it to the Chief of Staff, who presents it to you for a decision, or the Foreman files it as a finding in the intake. So each part ends with findings or recommendations back in the intake: often several findings from QA, bugs from implementation, a process-improvement CR from release; from there the loop starts again. At any time, chantier order drop moves a CR to 6-trash, with its work. The chantier CLI gives guidance and feedback to agents and writes a human-readable STATUS.md.

## Header

```md
## 🔄 Life of a change request

Every Change Request (CR) lands in one Markdown file; the CR folder moves and is enriched with prototype, spec and reports.
A CR is usually implemented in a pull or merge request (PR/MR).
Some CRs do not translate to a PR.
```

## Legend

```md
👤 you
🤵 Chief of Staff
🔥 Griller (optional)
👷 Foreman (🤵 Chief of Staff in direct mode)
🚜 driver
🔨 worker · ✍️ spec-writer
⌨️ chantier CLI
📄 file · 📁 folder
📨 intake
```

## Lanes

```md
PLANNING
QUALITY ASSURANCE
IMPLEMENTATION
RELEASE
PAUSE
```

## Intake (red)

```md
## 📨 Intake

🎫 Jira issue
🦊 GitLab · GitHub
💬 chat
📝 Markdown file
📝 findings

kept as received,
never edited
```

## chantier file

```md
chantier
file
```

## 01-intent.md

```md
## 📄 01-intent.md

the request,
summarised

in 1-inbox/
```

## Triage

```md
## ⚖️ Triage

🤵 or 🔥
with you
```

## Griller (optional note in the planning lane)

```md
## 🔥 Griller, optional

another session of yours,
same planning, never a batch
```

## Triage branches (blue pills)

```md
drop
⚡ automatable · short spec
📐 needs a spec
❓ needs clarification
```

## 6-trash

```md
🗑️ 6-trash/
```

## Spec loop

```md
## ✍️ spec-writer writes

03-change-spec.md
🤵 or 🔥 starts it on your word
```

```md
## 👤 you review

the spec
```

```md
✏️ needs revision
✅ approved
```

## Prototype (note beside the review)

```md
## 🎨 prototype

the destination, shown: a UI mockup, a vibe-coded app…
often made by you, outside this cycle
```

## Clarification loop

```md
## 🤵 or 🔥 grills you

with recommended answers
```

```md
## 👤 you answer

→ 02-answers.md
```

```md
↩ triage again
```

## chantier triage

```md
chantier triage
```

## 2-backlog

```md
## 📋 2-backlog/

P1…P4, set by you
```

## 3-ready

```md
chantier triage --ready
```

```md
## 🧰 3-ready/

waiting for the next batch
```

## Your go

```md
## 👤 your go

on the CRs you pick
```

## Opens the batch

```md
## 🤵 opens the batch

4-batch/
```

## Foreman

```md
## 👷 Foreman

processing queue · starts every driver
```

```md
⏱ /loop · chantier status --refresh
chantier open
chantier take
```

## CR driver

```md
## 🚜 CR driver

worktree · isolated branch
```

## Investigator (optional)

```md
## 🔦 Investigator

when the code is unfamiliar
```

## Rounds

```md
## 🔨 Coder

implement the spec
```

```md
## 📏 Inspector

review against the spec
```

```md
## implem. approved?
```

```md
no
🔁 FIX-REQUIRED → next round (≤ 3)
yes
rounds out
```

## Blocked

```md
## ⛔ blocked

question, approval, budget…
```

```md
🚜 CR driver
asks Foreman
```

## Bug found

```md
## 🐞 bug found

outside the CR's scope
```

```md
👷 Foreman
files bugs as findings
```

```md
## 🤵 Chief of Staff

asked by Foreman; may raise to you
```

```md
👷 Foreman
may raise
```

```md
🤵 Chief of Staff
orders
```

## Ship

```md
## 🚀 push · PR

rebase, gate, ship
```

```md
## 🧪 CI

green?
```

```md
## ✅ Verifier

at the pushed head
```

```md
🔴 a new round
```

```md
## 🚜 handback

ready + PR link
```

## Stack (optional)

```md
## stacked?
```

```md
yes
no
```

```md
## 🧱 Stack driver

order · restack · ship · heavy CI
```

```md
✅ ready, per CR
```

```md
## 👤 you merge
```

```md
## 📦 3-done/

on `order merged`
```

## QA (optional)

```md
👤 You
ask for QA
```

```md
## 🔍 QA?
```

```md
## 🦺 QA driver

uses the project's head as a user
```

```md
📝 findings
```

## Release

```md
chantier take
```

```md
👷 Foreman
merges release PR on release go
```

```md
## 🚚 Release driver

runs your procedure · checks
```

```md
## 🚀 released?
```

```md
📝 fix-<n>.md
✅ yes
```

```md
👤 your go
unless granted
```

```md
## 🧯 fix CR

fast track · ≤ 3 fixes per release
```

```md
## 🚜 CR driver

targeted fix
```

```md
## fix grant?
```

```md
yes
no
```

```md
👷 Foreman merges
within the granted budget
```

```md
👤 you merge
```

## After release

```md
## 📡 monitor deploys

(optional) · registry, pages…
```

```md
## 📝 retro.md

long-term fixes
```

```md
📝 recommendations
process improvement
```

```md
## 🚚 handback

ready · release link
```

```md
## 📦 3-done/

release CR
```

## Pause

```md
👷 Foreman
all merged or cancelled
```

```md
chantier pause
```

```md
## 📊 STATUS.md

exit report · cost to date
```

```md
👷 Foreman
sends final
```

```md
## 🤵 Chief of Staff

report + cost to date
```

```md
## 👤 your word

later, to close it
```

```md
chantier close
```

```md
then close --yes: each CR of 3-done/ → 5-archives/,
the batch's own files are deleted
```

```md
⏸️ the batch is paused; new work sets it running again
```

## Footer

```md
chantier CLI gives guidance and feedback to agents, writes human-readable STATUS.md.
The batch itself: running → paused → closed, in `batch-lifecycle.svg`.
At any time: `order drop` → `6-trash/`, with its work.
```
