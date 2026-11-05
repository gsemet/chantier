# A CR is a folder that moves

A change request is one folder of Markdown files in .agents/changes/; its life is that folder moving from stage to stage, never copied, and gaining files on the way. A request from the intake (a Jira issue, a GitLab or GitHub issue, the chat, a Markdown file) is filed with chantier file into 1-inbox/<slug>/, with intake/ as received and 01-intent.md, the request summarised; 02-answers.md holds your answers if you are grilled, 03-change-spec.md the spec. chantier triage moves a ready CR to 2-backlog/P1…P4/<slug>/; nothing new, you set its priority. On your go, chantier open moves it into a batch, 3-requests/<NN>-<batch>/<number>-<slug>/, where it gains STATUS.md and STATUS.json, written by the CLI; work/, written while it runs: notes, gate logs, the PR body, and for a release CR retro.md and fix-<n>.md; and evidence/, the QA and Verifier proofs. Once you merge it, chantier order merged moves it to 4-archives/<YYMMDD-HHMM>-<number>-<slug>/, kept as is. At any stage before the archive, chantier order drop moves it to 5-trash/, with its work.

## Header

```md
## 📁 A CR is a folder that moves

A CR is one folder of Markdown files in .agents/changes/. Its life is that folder moving from stage to stage, never copied.
On the way, the folder gains files.
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

the request, any source
```

## Moves (arrows between stages)

```md
chantier file            files it
chantier triage          ready
chantier open            on your go
chantier order merged    you merged
```

## Stage headers

```md
### 📥 1-inbox/
filed, not prioritised

### 📋 2-backlog/
under P1…P4/, prioritised by you

### 🏗️ 3-requests/
under <NN>-<batch>/, in a batch

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
📁 evidence/                        QA, Verifier proofs
```

## 4-archives folder (all carried)

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
📁 evidence/                        QA, Verifier proofs

nothing new · kept as is
```

## Trash (bottom)

```md
chantier order drop

### 🗑️ 5-trash/
dropped at any stage, with its work
```

## Footer

```md
Each move is a mv of the whole folder: same files, a new place, never a copy.
```
