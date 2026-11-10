# Life of a change request, in short

A change request (CR) is one folder in .agents/changes/ and usually becomes one pull or merge request (PR/MR). Agents do the work; you decide at four points: triage, spec, go and merge. Plan, with the Chief of Staff: a request from the intake (Jira, GitLab, GitHub, the chat or a finding) is filed in 1-inbox/; you triage it with the Chief of Staff (or a Griller, optional), who drops it or clarifies it; on your word the spec-writer, started by the Chief of Staff or a Griller, writes the spec, 03-change-spec.md, that you approve; it then waits in 2-backlog/ with a priority P1 to P4, or in 3-ready/ for the next batch, until your go. Build, run by the Foreman, or by the Chief of Staff in direct mode, in 4-batch/: one CR driver per CR, in its own worktree and branch, runs rounds of a Coder and an Inspector, at most 3; it rebases, passes the gate and ships a PR; CI and the Verifier check the pushed head, and a red result starts a new round. Merge: you merge the PR and the CR moves to 3-done/, then to 5-archives/ at close, with its retro and final status. Optional: the stack driver orders, restacks and ships stacked PRs; on your request a QA driver uses the project's head as a user; the release driver runs your release procedure, with at most 3 fix CRs. Out-of-scope bugs, QA findings and the release retro go back to the intake as findings. Each stage is a folder; the chantier CLI moves it. At any time, chantier order drop moves a CR to 6-trash/.

## Header

```md
## 🔄 Life of a change request, in short

One CR, one folder, usually one PR/MR. Agents do the work; you decide at four points: triage, spec, go, merge.
```

## Legend

```md
👤 you · 🤵 Chief of Staff · ✍️ spec-writer · 🔥 Griller (optional) · 👷 Foreman · 🚜 driver · 🔨 worker
```

## Phases

```md
PLAN · 🤵 Chief of Staff, or a 🔥 Griller (optional), with you
BUILD · 👷 Foreman runs the batch
or 🤵 the Chief of Staff, in direct mode
MERGE
```

## Plan

```md
## 📨 Intake

Jira, GitLab, GitHub,
chat, findings
```

```md
## ⚖️ Triage

🤵 or 🔥 with 👤 you
drop · clarify · spec
1-inbox/
```

```md
## 📐 Spec

✍️ spec-writer writes
03-change-spec.md
👤 you approve
1-inbox/
```

```md
## 📋 Backlog

P1…P4, set by you,
or waiting for the next batch
👤 your go starts it
2-backlog/ · 3-ready/
```

## Build

```md
## 🚜 CR driver

own worktree · branch
🔨 Coder ⇄ 📏 Inspector
4-batch/ · ≤ 3 rounds
```

```md
## 🚀 PR

rebase · gate · ship
🧪 CI · ✅ Verifier
4-batch/
```

```md
🔴 red → new round
```

## Merge

```md
## 👤 you merge

the PR/MR
→ 3-done/
```

```md
## 📦 Archived

retro · final status
at close
5-archives/
```

## Optional

```md
OPTIONAL
```

```md
## 🧱 Stack driver

orders, restacks, ships PRs
```

```md
## 🦺 QA driver

on request, uses
the head as a user
```

```md
## 🚚 Release driver

your procedure
≤ 3 fix CRs
```

## Findings

```md
🐞 out-of-scope bug
findings
retro
📝 findings go back to the intake
```

## Footer

```md
Each stage is a folder in .agents/changes/; the chantier CLI moves it. At any time: order drop → 6-trash/.
```
