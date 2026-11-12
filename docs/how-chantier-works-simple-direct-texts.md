# How chantier works (simple, direct mode)

In direct mode there is no Foreman session. You talk to one Chief of Staff, which reads the project's AGENTS.md: your rules and your gates; its Spec-writer writes the specification, on your word. On your go the Chief of Staff steers the batch itself and starts the Drivers; the CR driver runs short workers, any of which can be your own agent: Investigator, Coder, Inspector, which reads the diff before the commit, Verifier, which runs it at the pushed head, and Debugger; both the CR driver and the stack driver can run the conflict resolver. While a batch runs, the Chief of Staff's session holds no grill: an optional Griller, another session of yours, grills and specifies beside it.

## Header

```md
## 🏗️ How chantier works

Direct mode: the Chief of Staff steers the batch itself.
```

## Lanes

```md
MAIN SESSION
GRILLER
NO FOREMAN
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

/chantier:chief-of-staff · remote or direct
your session · plays the Foreman's role
direct mode
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
grills and specifies while the batch runs ·
/chantier:griller
```

## Direct mode

```md
no Foreman session:
the Chief of Staff
starts the Drivers itself
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

## Planning folder note

```md
**Planning folder**: .agents/changes/ in the project, or in an external surface.
```
