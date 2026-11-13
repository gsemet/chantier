# real-direct

The same campaign as [real-foreman](../real-foreman/RUNBOOK.md), steered in **direct mode**: no
Foreman session, the Chief of Staff steers the batch itself. This runbook does not repeat what
both share (the CRs, the user's turns, the audit and the report): it is real-foreman, except what
follows. The text common to the sandbox campaigns is in
[the evals README](../README.md#a-sandbox-campaign).

| | |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py real-direct <workspace>` (after `sandbox.py reset --yes`, see the README) |
| CRs | the same 5 frozen CRs as real-foreman |
| Open | the real-foreman line plus `--direct`: `$CHANTIER open <the five CRs> --mode <mode> --slots 3 --budget 20 --default-branch main --direct` (`setup.py` prints it) |
| Mode | chosen at launch, as in real-foreman |
| Team | the plugin's agents |

## Start

A new Code session of the Claude Desktop app on the workspace. The user pastes, with `<mode>` one
of `stack`, `parallel`, `series` and `<this checkout>` its absolute path:

```text
/chantier:chief-of-staff direct Run the chantier eval campaign real-direct in <mode> mode, in direct mode: follow <this checkout>/evals/real-direct/RUNBOOK.md.
```

From a terminal, in the workspace, the equivalent is:

```text
claude "/chantier:chief-of-staff direct Run the chantier eval campaign real-direct in <mode> mode, in direct mode: follow <this checkout>/evals/real-direct/RUNBOOK.md."
```

The words "in direct mode" repeat the skill's `direct` argument: the Chief of Staff's card takes
either one.

The session is new and its own: not a Foreman session. It is the steering session ("Steering a
batch yourself" in `chief-of-staff.md`): it runs `$CHANTIER preflight --direct`, `open --direct`,
claims its epoch, renames itself `[env] Project [Chief of Staff - Batch <nn> - Direct]`, starts
the Drivers itself and arms the heartbeat. It also plays the user in full, as in real-foreman.

The merge (`sandbox.py merge <n>`, from the workspace, alone), the question, the stuck CR and the
`budget:` ask (the raise is to `$30`: `$CHANTIER order budget --note 30`) are real-foreman's, as
the README says. In direct mode the Chief of Staff is the steering session: after its own `order
merged <cr> --epoch <n>` it fast-forwards the workspace's main checkout, which no longer stays at
the base (the audit's J26 reads it).

**The host's limits:** there is no Foreman session, so no message goes between Desktop sessions
and the 10-message limit does not apply to this batch. Should a send between sessions be refused
anyway, report it as `full` and real-foreman say (J15), and never send another way.

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

## Audit and report

`uv run --no-project python evals/kit/audit.py <workspace> --sandbox`, before `close --yes`. The
batch's `steering` is `direct`, and the audit reads the Chief of Staff's transcript as the
steering session, from its claim on: what the Chief of Staff started for itself outside the batch
is listed apart and not audited. Then the cost, as in real-foreman. The report goes in
`results/real-direct-<date>-run<n>.md`. Its first run follows the CR that rebuilt this campaign on
the sandbox.
