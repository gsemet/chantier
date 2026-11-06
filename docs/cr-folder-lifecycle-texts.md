# A CR is a folder that moves

A change request is one folder of Markdown files in .agents/changes/; its life is that folder moving from stage to stage, never copied, and gaining files on the way. A request from the intake (a Jira issue, a GitLab or GitHub issue, the chat, a Markdown file, or QA and retro findings) is converted to Markdown and filed with chantier file into 1-inbox/<slug>/, with intake/ as received and 01-intent.md, the request summarised; 02-answers.md holds your answers if you are grilled, 03-change-spec.md the spec. chantier triage moves a ready CR to 2-backlog/P1…P4/<slug>/; nothing new, you set its priority. To start its implementation, chantier open moves it into a batch, 3-requests/batch-<n>/<number>-<slug>/, where it gains STATUS.md and STATUS.json, written by the CLI; work/, written while it runs: notes, gate logs, the PR body, and for a release CR retro.md and fix-<n>.md; and evidence/, the Verifier's proofs. Once its PR or MR is merged, chantier order merged moves it to 4-archives/<YYMMDD-HHMM>-<number>-<slug>/, where it gains retro.md, its retro and final status. At any stage before the archive, chantier order drop moves it to 5-trash/, with its work.

## Header

```md
## 📁 A CR is a folder that moves

A CR is one folder of Markdown files in .agents/changes/.
Folder moves from stage to stage, never copied, gaining files on the way.
```

## Legend (top right)

```md
new in this stage
carried along
```

## Intake (left box)

```md
### 📨 Intake

🎫 Jira issue
🦊 GitLab · GitHub
💬 chat
📝 Markdown file
📝 QA / Retro findings

the request, any source
```

## Moves (arrows between stages)

```md
chantier file            convert to markdown
chantier triage          ready
chantier open            start implem.
chantier order merged    PR/MR merged
```

## Stage headers

```md
### 📥 1-inbox/
filed, not prioritised

### 📋 2-backlog/
under P1…P4/, prioritised by you

### 🏗️ 3-requests/
under batch-<n>/, in a batch

### 📦 4-archives/
merged, named by the merge time
```

## 1-inbox folder (all new)

```md
📂 <slug>/

📁 intake/              as received
📄 01-intent.md         summarised
📄 02-answers.md        your answers
📄 03-change-spec.md    the spec
```

## 2-backlog folder (all carried)

```md
📂 <slug>/

📁 intake/              as received
📄 01-intent.md         summarised
📄 02-answers.md        your answers
📄 03-change-spec.md    the spec

nothing new · you set P1…P4
```

## 3-requests folder (new: STATUS, work/, evidence/)

```md
📂 <number>-<slug>/

📁 intake/                          as received
📄 01-intent.md                     summarised
📄 02-answers.md                    your answers
📄 03-change-spec.md                the spec
📄 STATUS.md, .json                 where it stands
📁 work/                            while it runs
  └ notes · gate logs · PR body
  └ retro.md · fix-<n>.md          release CR
📁 evidence/                        Verifier proofs
```

## 4-archives folder (new: retro.md)

```md
📂 <YYMMDD-HHMM>-<number>-<slug>/

📁 intake/                          as received
📄 01-intent.md                     summarised
📄 02-answers.md                    your answers
📄 03-change-spec.md                the spec
📄 STATUS.md, .json                 where it stands
📁 work/                            while it runs
  └ notes · gate logs · PR body
  └ retro.md · fix-<n>.md          release CR
📁 evidence/                        Verifier proofs
♻️ retro.md                         Retro / status
```

## Trash (bottom)

```md
chantier order drop

### 🗑️ 5-trash/
dropped at any stage, with its work
```
