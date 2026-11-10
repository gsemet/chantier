# How chantier works (simple, Foreman mode)

In Foreman mode a nested Foreman session steers each batch. You talk to one Chief of Staff, which reads the project's AGENTS.md: your rules and your gates; its Spec-writer writes the specification, on your word. On your go the Chief of Staff starts one Foreman session per batch of changes; the Foreman starts Drivers; the CR driver runs short workers, any of which can be your own agent: Investigator, Coder, Inspector, which reads the diff before the commit, Verifier, which runs it at the pushed head, and Debugger; both the CR driver and the stack driver can run the conflict resolver. An optional Griller, another session of yours, grills and specifies the backlog beside the Chief of Staff.

## Header

```md
## 🏗️ How chantier works

Foreman mode: a Foreman session steers each batch.
```

## Lanes

```md
MAIN SESSION
GRILLER
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

/chantier:chief-of-staff
your session · stays free to talk while the batch runs
```

## Spec-writer

```md
✍️ Spec-writer
writes the spec,
in the background,
on your word
```

## Griller (optional)

```md
## 🔥 Griller

optional
another session of yours ·
grills and specifies the backlog ·
/chantier:griller
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
