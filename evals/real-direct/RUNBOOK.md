# real-direct

The same campaign as [real-foreman](../real-foreman/RUNBOOK.md), steered in **direct mode**: no
Foreman session, the Chief of Staff steers the batch itself. This runbook does not repeat what
both share (the CRs' rules, "Nothing merges", the audit, the report and what follows it): it is
real-foreman, except what follows.

| | |
| --- | --- |
| CRs | fresh items: the two `3-ready` CRs prepared for real-foreman are not taken here |
| Open | the real-foreman line plus `--direct`: `$CHANTIER open <A> <B> … --mode parallel --default-branch main --slots 3 --budget 20 --direct` |
| Team | the plugin's agents |

## Start

A new Code session of the Claude Desktop app on this repository's main checkout, on `main`. The
user pastes:

```text
/chantier:chief-of-staff direct Run the chantier eval campaign real-direct, in direct mode: follow evals/real-direct/RUNBOOK.md.
```

From a terminal, at the root of the main checkout, the equivalent is:

```text
claude "/chantier:chief-of-staff direct Run the chantier eval campaign real-direct, in direct mode: follow evals/real-direct/RUNBOOK.md."
```

The words "in direct mode" repeat the skill's `direct` argument: the Chief of Staff's card takes
either one.

The session is new and its own: not the Chief of Staff session that already runs this
repository's backlog, and not a Foreman session. It is the steering session ("Steering a batch
yourself" in `chief-of-staff.md`): it runs `$CHANTIER preflight --direct`, `open --direct`, claims
its epoch, renames itself `[env] Project [Chief of Staff - Batch <nn> - Direct]`, starts the
Drivers itself and arms the heartbeat. As in real-foreman, save the main checkout's `git status`
right after `open`, in `.agents/changes/4-batch/porcelain-at-open.txt`.

**The host's limits:** there is no Foreman session, so no message goes between Desktop sessions
and the 10-message limit does not apply to this batch.

## What it proves on top of real-foreman

The direct-mode lines that `hosts/claude-code.md` marks unproved:

- a Driver's `SendMessage` to `main`;
- the heartbeat in the Chief of Staff's own session;
- the `Chief of Staff, steering the batch` cost row (the steering share of the scorecard reads
  it);
- a refused force push, judged and run by the Chief of Staff with the Driver told by note, if one
  happens;
- `order qa` refused while the batch runs.

The report names each unproved host line it saw work.

## Audit

`uv run --no-project python evals/kit/audit.py . --real`. The batch's `steering` is `direct`, and
the audit reads the Chief of Staff's transcript as the steering session, from its claim on: what
the Chief of Staff started for itself outside the batch is listed apart and not audited. It runs
before any merge, `pause` or `close`, like the real-foreman audit. The report goes in
`results/real-direct-<date>.md`.

## After the report

As in real-foreman, with no Foreman: the Chief of Staff records `order merged <cr>` or `order drop
<cr>` on the user's word and acts on it itself, keeps a CR still blocked at the report for a later
batch the way real-foreman says, then pauses with `$CHANTIER pause --epoch <n>`, gives the
Completion report, and closes on the user's word. Each PR is merged or closed within the day.
