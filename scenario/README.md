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
up, pauses); scripted Drivers create their worktree, commit, rebase, push and open their
PRs against the fake forge, and use the CLI for its record (`round`, `gate`, `ship`,
`handback`); the Chief of Staff steers with `chantier order`. The scripted agents prove the
frame, not the judgement: the checks are on what the CLI refuses, records and reports.

- preflight refusing Claude in VS Code and passing on Desktop with no setup and nothing written;
  its P10 warning on the recommended allow rules missing from the settings (it still passes),
  and `P10 ok` once they are in a temporary home's `.claude/settings.json`;
- the batch opened with the branch from `AGENTS.md`, each CR named a branch and a worktree that
  the Driver creates; `take` refused past the slots and the budget, `round` past the limit;
  nothing written outside the planning folder;
- hand-backs as state writes (refused before a PR is recorded), `ship` reporting what is off
  (uncommitted changes, a head not pushed, no long gate at it), a QA ordered during the batch,
  with its folder in the inbox, that holds no CR back and keeps the batch from pausing until done;
- dropping a live CR (its processes stopped), adding an item, an order applied at once and
  marked done, a note on a ready CR that the Foreman sends back with a Driver, more rounds
  granted, `slots 0` as a hold (its usage line says "0 holds"), a wider budget, a ready CR taken back only with a note;
- the three modes: `open --parallel` refused; parallel by default (`take stack` and `stack`
  refused, `order mode` refused, a rebase note on a ready CR after a merge, on the default
  branch); a series (the next CR waits for the previous one to be ready, starts on its branch,
  is rebased on the default branch once the previous one is merged; `order add` goes on top; a
  CR before its dependency refused at `open`); `order mode --note stack` turning a series into a
  stack at once, and refused anywhere else;
- a stack (`open --mode stack`) of independent CRs: all taken at once, each started on the default branch, then
  stacked afterwards by `stack` (`ship` records the default branch before, the CR under it
  after); a dependency changed with `order after` (refused on a CR not queued, an unknown CR or
  a cycle), a chain started on the ready CR's branch and undone by `--note -`;
- direct mode: `preflight --direct` and `open --direct` (a session id needed), `order add` and
  `order qa` refused, a direct batch from `open` to the pause, two CRs added to the paused batch, which stays paused until the first `take`, then paused again, and `close` (priced with one `Chief of
  Staff (steering)` row and a Chief of Staff line that leaves the steering window out, `close` not
  blocked by the Chief of Staff's own transcript but by a Driver that writes), then a Foreman
  claiming a later epoch from another transcript: the steering switches and the old epoch is refused;
- the seat: `seat take` refused to a second session, taken over only with `--over` naming the
  holder, the batch keeping both Chief of Staff transcripts, the new session claiming the epoch
  with the steering still direct, `seat leave`;
- a Foreman restart (the stale epoch refused), a lost Driver taken over from `handoff`; a Foreman
  started in a linked worktree stopping at its worktree check, before it claims its epoch: no CR
  taken, one ask;
- `pause` refused while PRs are open, then the pause after the user's merges and the Foreman's
  cleanup; `land` no longer a command; the long gate serialized, and held while the suite of a gate whose command died
  still runs;
- Claude cost by CR; Copilot cost breakdown (`Agent <type>` lines) and by CR, estimated calls, updates and failures;
- a planning surface (its own git repository, two projects, each clone and worktrees outside it,
  run on both forges after the in-project batch): a command at the surface exits 2 naming the
  projects, a missing clone fails preflight, init makes the planning folder and its
  .gitignore; a batch in each project at once, a second open on one refused, one seat per
  project; 	ake carries cli: with --project, clone: and rchive: (`not in the PR` for a
  project that sets it so); the surface's git lists the CR documents and never a local file (atch.json,
  events.jsonl, STATUS files, locks, seat.json, gate logs), the clone stays clean; ship says
  the archive is missing from the PR until it is there; order merged writes delivery.md;
  ules lists the project's instructions then the surface's; close archives the CR;
- prepared-CR filing, lifecycle moves, collisions and rollback;
- a release: added to a running batch (`order add --release`) it waits for each other CR, a
  later one too, then for the user's `order confirm` (voided by a CR added after, refused once
  it has started), and alone in its batch it needs none; an irreversible action refused then approved
  (a `go` that dies with its Driver), a fix CR that stops every `go` until it merges and a new
  attempt, a grant (the Foreman merging the fix and the release PR with the forge's CLI after
  `release go`, recorded with `order merged --epoch`; a merge the forge refuses; the budget;
  the number of releases), and a release PR merged on the user's approval;
- the event log, and the forge's call log: only the agents called it;
- a paused batch: `pause` printing the cost to date (the whole summary, not cut), recorded with a
  to-date line and one total in `STATUS.md`, a second `pause` refused, `order add` leaving it paused, `take` setting it
  running again, `close` on a running batch saying `pause` comes first, a call made after `pause`
  counted;
- an old batch: `batch.json` written by hand with `status: "landed"` and a `landed` time read as
  paused, one with `status: "open"` read as running, taken by `take` and paused by `pause`, each
  rewritten with the new words at the next write;
- closing on the user's word: `close` refusing, with and without `--yes`, a CR not merged, an
  open order, a stack agent, and a session file (any agent's, a Copilot one's, or one whose
  time is not measured) written in the last 5 minutes; a pricing failure and a missing
  Foreman transcript refused the same way; a reopened batch named as such; then the final cost
  printed (with a call made after the last `pause`) and the folder deleted by `close --yes`, the dropped CR's worktree and branch by the Chief of Staff's
  git.

The transcript goes to `scenario/results/<forge>-<time>.md` (not committed); exit 1 if any check
fails. Windows runs one check more than Linux: `close` on a folder in use, since elsewhere a file
in use does not stop a rename.
