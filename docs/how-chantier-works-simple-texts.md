# How chantier works (simple)

You talk to one Chief of Staff, which reads the project's AGENTS.md: your rules and your gates; its Spec-writer writes the specification, on your word. On your go the Chief of Staff starts one Foreman session per batch of changes (Foreman mode), or steers the batch itself in direct mode, with no Foreman session; the steering session starts Drivers; the CR driver runs short workers, any of which can be your own agent: Investigator, Coder, Inspector, which reads the diff before the commit, Verifier, which runs it at the pushed head, and Debugger; both the CR driver and the stack driver can run the conflict resolver.

## Header

```md
## 🏗️ How chantier works

One office to talk to; the agents do the work.
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

## Spec-writer

```md
✍️ Spec-writer
writes the spec,
in the background,
on your word
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
Foreman mode
```

## Direct mode

```md
🤵 direct mode:
the Chief of Staff
steers the batch itself,
no Foreman session
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

follows your
release procedure
```

## Workers

```md
🔦 Investigator
🔨 Coder
📏 Inspector
reads the diff,
before the commit
✅ Verifier
runs it, at the
pushed head
🔧 Debugger
➕ your agents
⛓️ Conflict
resolver
```

## Note under workers

```md
**Any role can run your own agent**, named in AGENTS.md.
```
