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
👷 Foreman
🚜 driver
🔨 worker
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
LANDING
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

with you
```

## Triage branches (blue pills)

```md
drop
⚡ automatable · short spec
📐 needs a spec
❓ needs clarification
```

## 5-trash

```md
🗑️ 5-trash/
```

## Spec loop

```md
## 🤵 writes the spec

03-change-spec.md
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
## 🤵 grills you

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

## Your go

```md
## 👤 your go

on the CRs you pick
```

## Opens the batch

```md
## 🤵 opens the batch

3-requests/
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
## 📦 4-archives/

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
## 📦 4-archives/

release CR
```

## Landing

```md
👷 Foreman
all merged or cancelled
```

```md
chantier land
```

```md
## 📊 STATUS.md

exit report · cost final
```

```md
👷 Foreman
sends final
```

```md
## 🤵 Chief of Staff

bilan + cost
```

```md
## 👤 your yes

to close the batch
```

```md
chantier close
```

```md
deletes the batch folder
```

## Footer

```md
chantier CLI gives guidance and feedback to agents, writes human-readable STATUS.md.
At any time: `order drop` → `5-trash/`, with its work.
```
