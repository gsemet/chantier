# The scripted scenario

One whole batch through the real CLI, with no model: a test of the frame the CLI gives the
agents, free and about two minutes per forge. The evals with real agents are in
[`evals/`](../evals/README.md).

```bash
just scenario
```

runs it on a fake `gh` (GitHub), then on a fake `glab` (GitLab). CI runs it on Linux, on each
pull request and each push to `main`. One forge alone:

```bash
uv run --no-project python scenario/run_scenario.py --forge gitlab [--verbose] [--keep]
```

In a temporary git repository with a bare origin, a scripted Foreman reads the batch's state
and does what its card leaves it (fills the slots, asks, merges what the user allowed, cleans
up, lands); scripted Drivers create their worktree, commit, rebase, push and open their
PRs against the fake forge, and use the CLI for its record (`round`, `gate`, `ship`,
`handback`); the Chief of Staff steers with `chantier order`. The scripted agents prove the
frame, not the judgement: the checks are on what the CLI refuses, records and reports.

- preflight refusing Claude in VS Code and passing on Desktop with no setup and nothing written;
- the batch opened with the branch from `AGENTS.md`, each CR named a branch and a worktree that
  the Driver creates; `take` refused past the slots and the budget, `round` past the limit;
  nothing written outside `.agents/changes/`;
- hand-backs as state writes (refused before a PR is recorded), `ship` reporting what is off
  (uncommitted changes, a head not pushed, no long gate at it), a QA ordered during the batch,
  with its folder in the inbox, that holds no CR back and keeps the batch from landing until done;
- dropping a live CR (its processes stopped), adding an item, an order applied at once and
  marked done, a note on a ready CR that the Foreman sends back with a Driver, more rounds
  granted, `slots 0` as a pause, a wider budget, a ready CR taken back only with a note;
- a stack of independent CRs: all taken at once, each started on the default branch, then
  stacked afterwards by `stack` (`ship` records the default branch before, the CR under it
  after); a dependency changed with `order after` (refused on a CR not queued, an unknown CR or
  a cycle), a chain started on the ready CR's branch and undone by `--note -`;
- a Foreman restart (the stale epoch refused), a lost Driver taken over from `handoff`; a Foreman
  started in a linked worktree stopping at its worktree check, before it claims its epoch: no CR
  taken, one ask;
- `land` refused while PRs are open, then landing after the user's merges and the Foreman's
  cleanup; the long gate serialized, and held while the suite of a gate whose command died
  still runs;
- Claude cost by CR; Copilot cost breakdown (`Agent <type>` lines) and by CR, estimated calls, updates and failures;
- prepared-CR filing, lifecycle moves, collisions and rollback;
- a release: it waits for the batch's other CRs, an irreversible action refused then approved
  (a `go` that dies with its Driver), a fix CR that stops every `go` until it merges and a new
  attempt, a grant (the Foreman merging the fix and the release PR with the forge's CLI after
  `release go`, recorded with `order merged --epoch`; a merge the forge refuses; the budget;
  the number of releases), and a release PR merged on the user's approval;
- the event log, and the forge's call log: only the agents called it;
- a landed batch: its cost marked not final and one total in `STATUS.md`, a second `land`
  refused, `order add` setting it running again, a call made after `land` counted;
- closing on the user's word: `close` refusing, with and without `--yes`, a CR not merged, an
  open order, a stack agent, and a session file (any agent's, a Copilot one's, or one whose
  time is not measured) written in the last 5 minutes; a pricing failure and a missing
  Foreman transcript refused the same way; a reopened batch named as such; then the final cost
  printed (with a call made after the last `land`) and the folder deleted by `close --yes`, the dropped CR's worktree and branch by the Chief of Staff's
  git.

The transcript goes to `scenario/results/<forge>-<time>.md` (not committed); exit 1 if any check
fails. Windows runs one check more than Linux: `close` on a folder in use, since elsewhere a file
in use does not stop a rename.
