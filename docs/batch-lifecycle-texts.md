# Life of a batch

One batch at a time: it is running, then paused, and closed only on your word. The states and the transitions are the same with a Foreman (Foreman mode: a Foreman session steers the batch, CRs join it while it runs, and your session stays free to grill, file and triage) and with the Chief of Staff steering the batch itself (direct mode: no Foreman session; less dynamic, no grill in that session while the batch runs, so you grill in a Griller session and file your ideas to the backlog). Running: on your go on the plan, chantier open (Foreman mode) or chantier open --direct (direct mode) creates the batch in 4-batch/, running; open is refused while a batch is not closed; chantier open with no CR creates the batch paused, with no CR: order add joins CRs and the first take sets it running. Drivers take the CRs on the free slots; each is worked, handed back, merged by you, or dropped. A running direct batch takes no grill in its session and no order qa; order add queues a specified CR, and a release CR and its fixes join. Paused: once every CR is merged or cancelled, the CLI removes the merged CRs' worktrees and branches (one whose agent is still held, or that git refuses, is kept and named) and pauses the batch itself; a note, a QA or a stack driver still pending holds the pause and chantier pause is run once they are done. Nothing runs; the cost to date is computed and shown; the batch's STATUS.md is its exit report; the Completion report goes to you. A paused batch, of either steering, takes new CRs: chantier order add adds new CRs, any number, and the batch stays paused; the first take (or an order qa) sets it running again, and it pauses again at the end, with the cost to date grown. It stays paused, however long, until you say "close the batch". Closed: only on your word. chantier close is the check: it refuses, naming the cause, while anything runs or nothing at all can be priced (calls of a model with no price are shown apart and the final cost is a floor); otherwise it shows the final cost and what goes. On your yes, chantier close --yes moves each merged CR from 4-batch/3-done/ to 5-archives/, deletes the batch's own files in 4-batch/, and the dropped CRs' worktrees and branches are removed with git. Without a yes, everything stays. Hold (order slots --note 0: no new Driver starts) is not a state.

## Header

```md
## 📦 Life of a batch

One batch at a time: running, then paused, closed only on your word.
```

## Two steerings

```md
SAME STATES, SAME TRANSITIONS, WITH EITHER STEERING
```

```md
## 👷 Foreman mode

a Foreman session steers the batch
CRs join while it runs (order add, order qa)
your session stays free: grill, file, triage
```

```md
## 🤵 direct mode

the Chief of Staff steers it from your session, no Foreman session
less dynamic: no grill in that session while the batch runs;
grill in a Griller session, and file your ideas to the backlog
```

## Into running

```md
## 👤 your go

on the plan
```

```md
open is refused while a batch is not closed
```

```md
chantier open with no CR: the batch is born paused, with no CR;
order add joins CRs, the first take sets it running
```

```md
chantier open
```

```md
👷 Foreman mode
```

```md
chantier open --direct
```

```md
🤵 direct mode
```

## Running

```md
## ▶️ running

Drivers take the CRs on the free slots;
each is worked, handed back,
merged by you, or dropped
```

```md
## 🤵 direct mode: while running

order add queues; order qa refused,
no grill in this session
```

## Running to paused

```md
✅ every CR merged
or cancelled
```

```md
automatic pause
```

```md
the CLI removes the merged
CRs' worktrees and branches,
then pauses the batch
```

## Paused

```md
## ⏸️ paused

nothing runs
📊 cost to date, computed and shown
📄 STATUS.md: the exit report
Completion report to you
takes new CRs, either steering
```

```md
stays paused, however long,
until you say “close the batch”
a factory batch: no close offered;
it waits for its next ready CR
```

## Paused to running

```md
chantier order add
```

```md
the first take (or order qa)
```

```md
new CRs join it, any number; the first take sets it running again; it pauses again at the end, the cost to date grown
```

```md
or, in a factory batch, triage --ready
```

## Paused to closed

```md
👤 only on your word
```

```md
the check,
then your yes
```

```md
a factory batch:
order factory off,
then the retro and the close
```

## Closed

```md
## ⏹️ closed

the batch's own files
in 4-batch/ are deleted

each merged CR moves from
3-done/ to 5-archives/

the dropped CRs'
worktrees and branches
are removed with git
```

## Closing

```md
## 🔒 Closing, only on your word

👤 you say “close the batch”
```

```md
chantier close
```

```md
the check
```

```md
refused, naming the cause, while anything runs
or the final cost cannot be priced;
otherwise: the final cost and what goes
```

```md
chantier close --yes
```

```md
👤 on your yes
```

```md
Without a yes, everything stays.
```

## Hold

```md
## ✋ hold is not a state

order slots --note 0: no new Driver starts
```
