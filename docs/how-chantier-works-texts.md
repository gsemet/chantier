


# How chantier works

You talk to one Chief of Staff, which reads the project's AGENTS.md: your rules and your gates.
On your go it starts one Foreman session per batch of changes, which starts Drivers; the CR driver runs short workers: Investigator, Coder, Inspector, which reads the diff before the commit, Verifier, which runs it at the pushed head, and Debugger. The project harness, AGENTS.md and its encoded rules, always prevails and can define custom agents or skills.

The chantier Python CLI frames them: the change-request lifecycle, the limits and the means to synchronise. It writes only in .agents/changes, as JSON and Markdown. It runs in Claude Desktop or a Copilot SDK host.

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
NESTED SESSION
DRIVERS
WORKERS
```

## AGENTS.md

```md
## 📐 AGENTS.md

your rules, your gates
```

## Chief of Staff

```md
## 🤵 Chief of Staff

your session · questions, prototypes, change requests
```

## Arrows Chief of Staff <-> Foreman

```md
📋 orders
🙋 asks
```

## Foreman

```md
## 👷 Foreman

one session per batch of changes · Opus 5.5 · orchestrates
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

open, take, ship, land
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

Claude Desktop · Copilot SDK host
```
