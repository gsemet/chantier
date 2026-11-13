# Batch modes

A batch has one of three modes. Parallel, the default: every CR starts from the default branch at once and every PR is on the default branch; the first one ready wins and the user merges in the order things become ready; after each merge, every PR still open is rebased onto the default branch and checked again. Series: the CRs have a precise order; the next CR starts once the previous one is ready, from the previous CR's pushed branch, and its PR is a draft; once the previous one is merged, the next one is rebased onto the default branch and turns ready; the Chief of Staff guides the user merge by merge; on request a series switches to a stack. Stack: parallel with a stack driver; every CR starts at once, the PRs go each on the previous one and the stack driver makes one native stack on the forge; the user merges it in one action from the top PR, the release last. A change inserted into a ready stack: the PRs above go back to draft, insert, restack, update the stack on the forge, verify, then the PRs turn ready.

## Header

```md
🔀 Batch modes
Three ways to relate the pull requests of one batch: who starts when, on which base, and who merges what, when.
```

## Parallel lane

```md
Parallel
(the default)
Ask: nothing, it is the default.
Every CR starts at once,
from the default branch.
The first one ready wins: you
merge in the order things
become ready, unless told
otherwise.
time
CR A
CR B
CR C
CR A on main
ready
you merge A
CR B on main
ready
rebase + checks
you merge B
CR C on main
rebase + checks
ready
rebase + checks
you merge C
After each merge, every open PR is rebased
onto main and its checks run again.
```

## Series lane

```md
Series
(on request)
Ask: "run these in series".
The CRs have a precise order.
The next one starts once the
previous one is ready, on its
branch, as a draft. After the
previous one merges, it is
rebased on main and turns
ready. The Chief of Staff
guides you merge by merge.
time
CR A
CR B
CR C
CR A on main
ready
you merge A
CR B on A (draft)
rebase
ready
you merge B
CR C on B (draft)
rebase
ready
you merge C
On request: switch to a stack, at once (order mode --note stack):
every CR left starts together, each on the previous one.
```

## Stack lane

```md
Stack
(on request)
Ask: "build a stack of these".
Parallel, with a stack driver:
every CR starts at once, the
PRs go each on the previous
one, then one native stack on
the forge. You merge it in one
action from the top PR.
time
CR A
CR B
CR C
CR A on main
CR B on main
CR C on main
stack
driver
stacks
ready on main
ready on A
ready on B
you merge the stack, once
one stack on the forge, merged from the top PR, release last
insert: drafts above, insert, restack, stack, verify, ready
```

## Legend

```md
CR driver works
PR ready
PR draft or driver on a draft
rebase, checks, restack
you merge
```
