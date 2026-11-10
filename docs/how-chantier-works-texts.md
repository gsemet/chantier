# How chantier works

A CR is a change request: an idea, a bug, a feature, an intent. You talk to one Chief of Staff, which reads the project's AGENTS.md: your rules and your gates. An optional Griller, another session of yours, grills and specifies the backlog beside the Chief of Staff. On your word that a CR is grilled enough, its Spec-writer writes the Change Specification, in the background. On your go the Chief of Staff starts the batch in one of two modes. In Foreman mode, a nested session, one Foreman per batch, not recommended in a remote session, the conversation with the Chief of Staff stays fully dynamic and natural. In direct mode the Chief of Staff plays the Foreman's role in the same session: it works in a remote session, but it cannot grill while the batch runs, so use a Griller session. The steering session starts Drivers; the CR driver runs short workers: Investigator, Coder, Inspector, which reads the diff before the commit, Verifier, which runs it at the pushed head, and Debugger. The project harness, AGENTS.md and its encoded rules, always prevails and can define custom agents or skills. The chantier Python CLI frames them: the change-request lifecycle, the limits and the means to synchronise. It writes only in .agents/changes, as JSON and Markdown. Foreman mode runs in Claude Desktop or a Copilot SDK host; direct mode in any Claude Code entry point or a Copilot agent session.

## Header

```md
## 🏗️ How chantier works

One office to talk to; the agents do the work.
```

## Unit of work (top right box)

```md
## **CR** = Change Request

an idea, a bug, a feature, an intent
```

## Lanes

```md
MAIN SESSION
GRILLER
STEERING
DRIVERS
WORKERS
```

## AGENTS.md

```md
## 📐 AGENTS.md

your rules, your gates
```

## Spec-writer

```md
✍️ Spec-writer
writes the Change Specification,
in the background, on your word
```

## Chief of Staff

```md
YOU
```

```md
## 🤵 Chief of Staff

/chantier:chief-of-staff · direct
your session · questions, prototypes, change requests
```

## Griller (optional)

```md
## 🔥 Griller

optional
another session of yours ·
grills and specifies the backlog,
beside the Chief of Staff
/chantier:griller
```

## Arrows Chief of Staff <-> Foreman mode

```md
📋 orders
🙋 asks
```

## Arrow Chief of Staff -> direct mode

```md
same session
```

## Foreman mode (left half)

```md
## 👷 Foreman mode

a nested session · Opus 5.5 · one per batch
fully dynamic, natural talk with the Chief of Staff
not recommended in remote
```

## Direct mode (right half)

```md
## 🤵 direct mode

the Chief of Staff plays the Foreman's role
works in a remote session
no grill while the batch runs:
use a 🔥 Griller session
```

## Drivers

```md
## 🚜 CR driver

takes one CR
to completion
```

```md
## 🧱 Stack driver

responsible for
PR/MR stacks
```

```md
## 🦺 QA driver

tests like a user
```

```md
## 🚚 Release driver

follows your procedure
monitors deployment
```

## Workers

```md
🔦 Investigator
🔨 Coder
📏 Inspector
reads the diff, before the commit
✅ Verifier
runs it, at the pushed head
🔧 Debugger
➕ your agents
```

## Note under workers

```md
**Project harness** (AGENTS.md, encoded rules) always prevails and can define custom agents or skills.
```

## Storage

```md
## 🗄️ .agents/changes/, as JSON and Markdown

1-inbox → 2-backlog → 3-requests → 4-archives · 5-trash
```

## chantier CLI

```md
## chantier

Python CLI
```

```md
## 🔄 CR lifecycle

open, take, ship, pause
```

```md
## 🚧 Limits

slots, budget, rounds
```

```md
## 📣 Sync

order, status
```

## Coding Agents

```md
## Coding Agents

👷 Foreman mode
Claude Desktop · Copilot SDK host
🤵 direct mode
any Claude Code entry point ·
Copilot agent session
```
