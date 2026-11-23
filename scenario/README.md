# The scripted scenario

One whole batch through the real CLI, with no model: a test of the frame the CLI gives the
agents, free. It runs as nine independent units, four at a time, each in a workspace of its own.
The evals with real agents are in [`evals/`](../evals/README.md).

```bash
just scenario
```

runs every unit: eight on a fake `gh` (GitHub) and one, `gitlab`, on a fake `glab` (GitLab). CI
runs it on Linux, on each pull request and each push to `main`. The units, and what runs of them:

```bash
uv run --locked python scenario/run_scenario.py --unit gates --unit stack   # these units only
uv run --locked python scenario/run_scenario.py --jobs 8                    # eight at a time
uv run --locked python scenario/run_scenario.py --unit gitlab --verbose --keep
```

`--unit` is repeatable, `--jobs` sets how many units run at once (4 by default), `--forge` keeps
one forge, `--verbose` prints a single unit's transcript live and `--keep` keeps the workspaces.
A unit is one child process: it builds its own temporary git repository with a bare origin, runs
its cases in order and writes its transcript and its JSON. A unit over its budget (a literal in
`UNITS`, in seconds) only warns; a unit that hangs, past the larger of 600 s and four times its
budget, is killed with its processes and fails the run, as does any failed check. The run prints
one row per unit (checks, commands, seconds, budget, status), the wall time and the sum of the
units' seconds, and exits 1 on a failed check, a crash or a hang.

Results are not committed. A run writes `scenario/results/scenario-<stamp>-<pid>.md` (the table,
the warnings and every unit's transcript) and, beside it, one folder
`scenario/results/<stamp>-<pid>/` holding each unit's `<unit>-<forge>.md` (its transcript, with a
timing table by case) and `<unit>-<forge>.json` (checks, failed labels, commands, seconds). Windows
runs one check more than Linux, in `release`: `close` on a folder in use, since elsewhere a file in
use does not stop a rename.

Measured on 2026-11-21 on a Windows 11 machine (Ryzen 7 7800X3D, 16 logical cores), two full runs
with `--jobs 4` (the default) at the same head, all checks passing except one in run B (below). The
machine was not proven idle: other chantier sessions share it, and a point sample of the CPU load
before each run read 25 percent for run A and 54 percent for run B.

A unit's budget is the slower of the two runs plus 25 percent, rounded up to the next 5 s. Under
load a unit may still go over its budget, and it then only warns, since a unit over its budget only
raises a warning.

| unit | budget (s) | run A (s) | run B (s) |
| --- | ---: | ---: | ---: |
| parallel | 350 | 279.4 | 274.4 |
| stack | 750 | 598.1 | 531.7 |
| release | 585 | 464.4 | 396.6 |
| gates | 610 | 486.4 | 426.8 |
| series-deps | 380 | 284.6 | 301.2 |
| direct | 220 | 174.9 | 171.6 |
| surface-board | 710 | 527.9 | 490.6 |
| qa-driver | 255 | 182.9 | 200.1 |
| gitlab | 115 | 72.5 | 91.8 |
| wall time | | 781.0 | 754.1 |
| sum of the units | | 3071.1 | 2884.8 |

In run B, `surface-board` failed one check ("the server reads the forge once per cycle for the one
project with an open PR, and no second hub reads", 284 of 285); alone, minutes later, it passed
285 of 285 in 424.0 s. The failure depends on the load of the machine.

The target of under 300 s on a quiet machine and on Linux CI is not proven: no run came under 300 s,
and a quiet Linux machine, where a process starts much faster than on Windows, has to confirm it
and lower the budgets.

In a unit, a scripted Foreman reads the batch's state and does what its card leaves it (fills the
slots, asks, merges what the user allowed, cleans up, pauses); scripted Drivers create their
worktree, commit, rebase, push and open their PRs against the fake forge, and use the CLI for
its record (`round`, `gate`, `ship`, `handback`), passing `--lease <n>`, the number `take` printed
(the World keeps it); the Chief of Staff steers with `chantier
order`. The scripted agents prove the frame, not the judgement: the checks are on what the CLI
refuses, records and reports. What the CLI only refuses on a prepared state is checked by pytest
in `skills/chantier/scripts/cli/tests/` (in-process, parametrized, in `just test`), not here.

## Coverage

Each bullet ends with the unit that runs it, `(unit: <name>)`, and/or the pytest test that
checks it, `(test: <file>::<test>)`. A bullet with neither fails `test_scenario_coverage.py`, as
does a unit that is not in `UNITS` and a test that does not exist.

- preflight refusing Claude in VS Code and passing on Desktop with no setup and nothing written;
  its P10 warning (one line per capability the batch uses) on the recommended allow rules missing
  from the settings (it still passes), and `P10 ok` once they are in a temporary home's
  `.claude/settings.json`, and the release rules named by `preflight --autonomous-releases 1`
  (it still passes); P10 (GitHub run, `--mode stack`) naming `gh stack view` only when the fake
  `gh extension list` names `github/gh-stack` (a `gh-stack` folder no longer counts) (unit:
  parallel) (test: test_cli_runs.py::test_preflight_warns_on_missing_allow_rules_and_never_fails_on_them);
- the batch opened with the branch from `AGENTS.md`, each CR named a branch and a worktree that
  the Driver creates; `take` refused past the slots and the budget, `round` past the limit;
  nothing written outside the planning folder (unit: parallel, gates) (test:
  test_rail_refusals.py::test_slots_zero_holds_and_a_spent_budget_stops_the_next_driver_until_it_is_raised);
- a stray second `round` refused (exit 2, the count unchanged, no `round` event) and passing after
  a `note`; a `round` passing with no note when the worktree's head, or its untracked files,
  changed since the last one; `note` printing `context: not measured (no agent recorded)`, then
  `context: <n> tokens (agent <id>)` from the end of a fake agent transcript, and `cost --by cr`
  showing the Driver's peak context and compactions on the CR's line (unit: parallel, gates)
  (test: test_rail_refusals.py::test_a_round_with_nothing_since_and_the_round_limit_are_refused_and_more_can_be_granted);
- the optional `chantier.yaml` (or `.yml`, never both), in layers (the surface root, the project's folder, the code repository; a plain `default` takes a weaker value back): none (the plugin's agents, no `team:` line), a valid one (the
  resolved model, recorded at `open`, printed by `take` and `playbook --batch`), kept by a running
  batch when the file changes, refused with its line and nothing moved (an unknown role or key, a
  tab, an anchor, a duplicate key, an unknown, ambiguous or version-only model name), the user's own
  agent plus a model on a host that cannot start a named agent with one (refused), and a model with
  no agent on that host (a generic agent: `agent=(generic)`, its contract printed by `take`); the `long_gate:` key refused with its line by `gate`,
  `playbook` and preflight P12 (test:
  test_playbook_config.py::test_open_refuses_a_bad_chantier_yaml_at_its_line_and_moves_nothing)
  (test: test_playbook_config.py::test_a_valid_file_is_resolved_recorded_and_kept_by_the_running_batch)
  (test: test_gate_refusals.py::test_a_bad_long_gate_key_is_refused_with_its_line_by_gate_playbook_and_preflight);
- hand-backs as state writes (refused before a PR is recorded), `ship` reporting what is off
  (uncommitted changes, a head not pushed, no long gate at it) and refusing, with nothing recorded, a
  branch that holds a merge commit among the CR's own commits, a QA ordered during the batch,
  with its folder in the inbox, that holds no CR back and keeps the batch from pausing until done;
  its refusals (no request, a spent budget, its folder not opened) in pytest (unit: parallel,
  gates, qa-driver) (test:
  test_rail_refusals.py::test_order_qa_needs_a_request_and_a_budget_and_its_folder_is_not_opened);
- `verdict VERIFIED` refused without `work/verify.md` naming the head (no file, a stale `Head:`),
  `NOT VERIFIED` accepted without it (unit: gates)
  (test: test_verdict_note.py::test_verified_needs_a_verify_note_naming_the_head);
- leases (unit: parallel): a stale `--lease` exits 3 `claim lost` and a missing one
  exits 2, nothing recorded; a `lease <cr> hold` keeps the lease live through its minutes (`CHANTIER_LEASE_TEST_MINUTE`), with no process running, and one given a `--` command is refused;
- the step a working CR is at: `round` recording `coder r1`, `phase` recording the inspector, a
  gate with its detail, `ci`, in the CR's STATUS.json, the batch row, `chantier status` and
  STATUS.md, the `phase` event outside the Progress steps, the step cleared by `handback` and
  `take`; the read data of the board naming `phase` and `next_to_start` (none with the budget
  spent); `phase` refusing a queued CR, a `review` with no detail and a detail
  past 40 characters in pytest (unit: parallel, surface-board) (test:
  test_rail_refusals.py::test_phase_refuses_a_queued_cr_a_review_with_no_detail_and_a_long_detail);
- dropping a live CR to the trash (`order drop --note trash`, then `cancel`: its processes stopped), a CR
  added to a running direct batch dropped to the backlog P3 (its folder `2-backlog/P3/<number>-<slug>` with
  `formerly.json`, `⚪ dropped to 2-backlog/P3` in its STATUS.md, a CR added after it numbered above it),
  then dropped to `ready` (its folder `3-ready/<number>-<slug>` with `formerly.json`, `⚪ dropped to
  3-ready` in its STATUS.md) and brought back by `order add` under its number, `order drop --note
  inbox` refused for any CR,
  adding an item, an order applied at once and
  marked done, a note on a ready CR that the Foreman sends back with a Driver, more rounds
  granted, `slots 0` as a hold (its usage line says "0 holds"), a wider budget, a ready CR taken
  back only with a note (unit: parallel, gates) (test:
  test_rail_refusals.py::test_a_ready_cr_goes_back_to_a_driver_only_with_a_note_and_cancel_needs_the_epoch);
- the three modes: `open --parallel` refused; parallel by default (`take stack` and `stack`
  refused, a rebase note on a ready CR after a merge, on the default branch); a series (the next
  CR waits for the previous one to be ready, starts on its branch, is rebased on the default
  branch once the previous one is merged; `order add` goes on top; a CR before its dependency
  refused at `open`); `order mode --note parallel|series|stack` switching a running batch between
  any two modes at once (the order by readiness, then the others, the chains kept; a merged CR's
  record unchanged; a leaving stack clearing every place; the rebase base each target prints), and
  `forge-stack unstack` dissolving the open stack and retargeting each open PR to the base the new
  mode gives (GitHub), or only retargeting (GitLab) (unit: series-deps, stack, gitlab) (test:
  test_mode_switch.py::test_to_a_stack_the_ready_cr_go_first_in_the_order_they_became_ready)
  (test: test_mode_switch.py::test_a_chain_is_kept_when_the_switch_would_put_a_cr_below_its_dependency)
  (test: test_mode_switch.py::test_leaving_a_stack_clears_every_place_in_it);
- the early conflict check: the scripted Foreman runs `git merge-tree --write-tree` for a CR handed
  back ready against each other ready PR of a parallel batch, asks once (`conflict <cr> with <cr>:
  <paths>; switch to a stack?`) and notes the pair on a conflict, sends nothing when two PRs do
  not conflict, asks again for no pair already noted, and checks nothing in a stack batch; the
  switch to a stack then puts the earlier ready CR at the bottom (unit: series-deps) (test:
  test_mode_switch.py::test_to_a_stack_the_ready_cr_go_first_in_the_order_they_became_ready);
- `order mode` refusing the mode the batch already has and an unknown one, nothing written (test:
  test_mode_switch.py::test_the_same_mode_and_an_unknown_one_are_refused_and_nothing_is_written);
- a stack batch's first `take stack` made due: `status` prints one `stack: take stack now: <crs> ready
  with a PR, ...` line while two CRs or more are ready with a PR and none was ever stacked, with no
  stack driver (absent with one recorded, after `stack` marks the CRs, and after a merge is recorded;
  a reminder only) (unit: stack) (test: test_stack_due.py::test_the_first_stack_is_due);
- a stack batch's shape: `status --refresh` prints one `shape stack:` line (next step, stack driver,
  native stack, alone asks, the rules card) and none in a parallel batch; a per-CR `ready-to-merge`
  for a CR with another open PR in the chain is refused (exit 2, nothing recorded), `--outside-stack`
  without an open order on the CR is a usage error, and the Foreman waits for the stack (unit:
  stack, series-deps, qa-driver) (test: test_stack_shape.py::test_the_guard_refuses_a_cr_that_is_not_alone);
- a stack (`open --mode stack`) of independent CRs: all taken at once, each started on the
  default branch, then stacked afterwards by `stack` (`ship` records the default branch before,
  the CR under it after, and refuses a CR whose branch does not hold the recorded head of the CR under it, recording nothing); a CR starting on the nearest earlier CR with a PR (a ready one only; a working or blocked
  one, or a lower ready one past it, gives the default branch, a CR with an `after` is on its
  dependency's branch whatever ready CR sits above it, and a taken CR whose start CR has ended
  prints the default branch; a branch with no PR, a
  cancelled or merged CR skipped, and a CR whose PR the forge shows merged: the hub's `merged@1` line
  of the journal, run on the fake forge, with `take` and `handoff` printing the default branch and a
  `base:` line, until `order merged`; with no journal line, a's branch as before; a fix, a release, a CR with an `after` and a parallel batch
  unchanged), recorded at its first take (the default branch once its CR is cancelled or the batch leaves the
  stack), a working PR off its place left out of the stack as it stands (`show`, `stack`, a
  refusal at the bottom) and `forge-stack create` retargeting before it stacks (the fake forge
  refuses, as GitHub does, a stack whose PR is not on the previous PR's head); a dependency changed with `order after` (refused on a CR not queued, an
  unknown CR or a cycle; the message names `stack` in a stack batch), a chain started on the ready
  CR's branch and undone by `--note -`; a stacked CR with an `after` taking its place in the
  stack as base (`stack` and `ship`), `stack` with no CR printing what `take stack` printed and
  writing nothing with a stack driver recorded, and `ship` naming the `work/pr-body.md` lines
  whose SHA left the head's history after a rebase (the SHA after `carried from` and the text of `STALE` lines left out; an image, Markdown or HTML, linked into a commit outside the head named on any line, `STALE` lines included),
  and not taking a token of digits only for a commit (a dangling commit whose first seven
  characters are digits) (unit: stack);
- a ready CR held out of a stack (`order hold`, `order unhold`): the stack, `status` and `forge-stack rebuild`
  leave the held PR on the default branch as a draft, `take` and `stack --out-of-draft` refuse it, and
  `unhold` puts it back on top (unit: stack) (test: test_stack_hold.py::test_hold_leaves_the_cr_apart_and_unhold_puts_it_back_on_top)
- a working CR parked on an outside wait (`park`): it leaves the slots and the stack (`stack`, `status`
  and `forge-stack rebuild` leave it out, with the `parked:` line), `take` refuses it while its wait is
  open, and once the wait is cleared `take` brings it back on top of the stack (unit: stack) (test: test_park.py::test_park_leaves_the_stack_and_take_brings_it_back_on_top)
- `order hold` of a live CR in every batch mode: the CR is blocked and held, its slot is left to the Foreman, `status` prints the `held:` line, `unhold` brings it back blocked (unit: stack) (test: test_hold_live.py::test_a_working_cr_is_held_in_every_mode_and_comes_back_blocked)
- a stack's long-gate waiver (`order waive stack`): a lower CR handed back ready with no gate and
  no `--no-gate` while the top is refused without its own, `handoff` printing the two `gate:`
  lines, `status`, `STATUS.md` and `STATUS.json` showing `waived → CR-k (#n)` and `validates …`,
  an `order add` on top moving the validation to the new CR, `order waive stack --note -` making a
  lower CR need its gate again while a CR already handed back keeps its waiver and the user's
  words, and a waiver of one CR of the stack not withdrawn alone; the refusals (outside a stack,
  a CR waiver with no `--follow-up` or a missing folder) and the `gate` object's states in pytest
  (unit: stack) (test: test_gate_waiver_orders.py::test_a_stack_waiver_is_refused_outside_stack_mode)
  (test: test_gate_waiver_orders.py::test_a_cr_waiver_needs_an_existing_backlog_folder)
  (test: test_gate_view.py::test_the_state_of_a_gate_read_from_the_gate_events_at_the_head);
- the three words of a ready CR (`ready locally`, `PR in draft`, `ready to merge`) with their
  icons 🟣, 🟤 and 🟢 in `status`, the STATUS files (`readiness`) and `handoff`, and the `stack` and
  `take stack` rows: the hand-back state and the PR's draft flag (`ready, PR draft (#n)`):
  `ship` reading the draft state from the forge, a CR the stack driver has not placed reading its word
  from its PR's base on the forge (`ready to merge` on the default branch or on the branch of a CR that is;
  `PR in draft` waiting for its turn out of draft, or on the CR under it; the chain's rule again with
  no recorded base and once `stack` places it), the hand-back line by word (for `PR in draft`, its PR's draft state and the CR (and PR) it waits
  on), a PR out of draft over a draft, `stack
  --out-of-draft` refused over a draft (nothing written) or on a CR that is working, `stack
  --out-of-draft` and `--draft` recorded, a CR taken back dropping the PR above it to `PR in
  draft`, a prepared release, a CR on an open CR's branch in a parallel batch, an old record with
  no draft state, a hand-edited ready CR with no `pr`, and no retired blue icon in any STATUS
  file; `forge-stack show` reads `ready to merge:` and check 4 compares the recorded draft state
  with the forge's (unit: stack);
- `forge-stack` (GitHub, against `fake_gh.py`, which also unstacks and reads and changes a PR's
  base, refusing the change while the PR is in an open stack): the stack as it stands (the bottom
  CRs with a PR, the others to come): `create` and `show` with two ready PRs and the release to
  come, naming the commit the user may merge below; a CR that joins as a draft on top (`rebuild`:
  unstack, retarget, create again; `drafts on top`, `to come:`; a working CR with a PR the stack driver has not placed, under `to come:`); `check 4` read against each CR's
  status; the complete stack (`stack complete, mergeable below`, no `to come:` line); `stack`
  naming only some CRs, refused when a dependency is left out; `rebuild` after an insertion
  (unstack, retarget, one new stack bottom to top, the release on top), after a partial merge
  (the first PR left to the default branch), stopped by a forge refusal and run again, stopped by
  a stack that stays open after five unstack tries (exit 4, `unstack_ignored`) and run again,
  the forge's empty unstack reply (`unstack_empty`: `rebuild` completes), the dissolved line on a
  failure after the unstack (its absence after the five tries) and `create` run after it, the
  unknown-state line when the create reply cannot be read (`create_unreadable`) and `show` run
  after it,
  idempotent with drafts as a line to act on, and refused on a GitLab link mixed into a GitHub
  stack (not all in one repository), on a link of neither shape, on a parallel batch and with no
  PR at the bottom of the stack; a dropped CR's PR still held by the forge's stack (`check 2: …
  dropped #n (<cr>): close it`, exit 2; `rebuild` unstacks naming it and posts the stack without
  it), a foreign PR still named `not in the batch's stack`; `stack` with no CR printing each
  row's `head` and `restack:` (the CR's last `restack:` note, else `restack: none`) and a last
  `context:` line (`not measured` with no transcript), which `take stack` does not print (unit:
  stack);
- `forge-stack` on GitLab (against `fake_glab.py`, which answers a merge request's read, the open
  MRs on a branch and a retarget from the state's `mrs`, and refuses the retarget with
  `retarget_refused`): the chain made by `create` (retarget off the record's base, bottom first,
  `--hostname`) and made again with nothing to retarget; `show` naming the commit, `to come:` and
  writing nothing; a CR that joins as a draft (`rebuild` retargets, no unstack); the three
  `check 4` forms; the wrong target (`check 3`), a foreign MR (`check 2`), a closed MR and an MR
  merged into the branch below (`check 1`, folded), an MR on the release's branch (`check 5`);
  the complete chain; a refused retarget (exit 4, the done lines first); `--stack` refused (unit:
  gitlab);
- direct mode: `preflight --direct` and `open --direct` (a session id needed), `order add` and
  `order qa` refused, a direct batch from `open` to the pause, two CRs added to the paused batch,
  which stays paused until the first `take` (its output ends with the `watch: not running` line,
  not indented, after the Driver prompt block), then paused again, and `close` (priced with one
  `Chief of Staff, steering the batch` row that keeps a turn which only names or reads a
  specification, a grill and specifications line and a whole-session line that holds the
  steering window and names it, `close` not blocked by the Chief of Staff's own transcript but by a Driver
  that writes), then a Foreman claiming a later epoch from another transcript: the steering
  switches and the old epoch is refused; the spec-writer and spec-critic transcripts on the grill
  line in pytest (unit: direct) (test:
  test_cost_reading.py::test_the_chief_lines_and_a_model_with_no_price) (test:
  test_cli_runs.py::test_a_direct_batch_is_recorded_shown_and_queues_added_work);
- a batch opened with no CR, born paused and ordinary (no `factory` key, no `Factory:` token in the
  brief, `status` saying `no CR yet` and how a CR joins it by `order add`), then the running batch
  in a direct batch: a CR being specified marked with `triage --running-batch` (nothing moves),
  `status` naming it `written` once specified, `order add` placing it in `1-pending` and clearing
  the mark, its end pausing the batch with the ordinary `next:` line (the retro, then the close
  offer), a second CR added before the close starting it again at the next `take`, `triage
  --ready` of a third CR leaving it in `3-ready`, and `order factory on` refused (unit: direct)
  (test: test_running_batch.py::test_any_other_destination_clears_the_mark);
- the seat: `seat take` refused to a second session, taken over only with `--over` naming the
  holder, the batch keeping both Chief of Staff transcripts, the new session claiming the epoch
  with the steering still direct, `seat leave` (unit: direct) (test:
  test_cli_runs.py::test_the_seat_is_one_file_held_until_taken_over_on_purpose);
- a Foreman restart (the stale epoch refused), a lost Driver taken over from `handoff`; a Foreman
  started in a linked worktree stopping at its worktree check, before it claims its epoch: no CR
  taken, one ask (unit: direct, qa-driver);
- `pause` refused while PRs are open, then the pause after the user's merges and the Foreman's
  cleanup; `land` no longer a command; the long gate serialized, and held while the suite of a
  gate whose command died still runs; a Driver's stop of its own running gate (`gate <cr> --stop`:
  recorded `stopped`, no pass, another CR's gate refused; its usage and `nothing to stop` in
  pytest) and a bare `cancel` refused without `--epoch` (in pytest), like every steering command
  (`foreman set`, `foreman transcript`, `status --stop-heartbeat`, `take`, `take stack`, `agents
  set`, `order done`, `pause`: exit 2, a message in the Foreman's number and not the word epoch,
  the record and the events untouched, in pytest), and a stale Foreman refused in the same words
  (unit: parallel, gates)
  (test: test_rail_refusals.py::test_a_steering_command_without_its_number_is_refused_and_writes_nothing)
  (test: test_gate_refusals.py::test_gate_stop_takes_no_command_and_gate_needs_one_and_nothing_running_is_not_an_error)
  (test: test_rail_refusals.py::test_a_ready_cr_goes_back_to_a_driver_only_with_a_note_and_cancel_needs_the_epoch);
- the long gate's queue running the next merge first (a stack's bottom CR, arriving last, passes
  before the CR waiting; the holder is not stopped), and a long gate and a verdict carried over a clean rebase
  (`ship` logs a `carry` event and `STATUS.md` shows `carried from <sha7>`; `handback` accepted with `gate_from` and `verdict_from`, no new gate and no new verdict; a restack of a ready CR carries again; CR-316's shape, a restack onto a rewritten branch of the CR under it, carries; a rebase resolved by hand, shipped with `--conflict`, is refused with `does not carry: the rebase resolved a conflict`; the old-git refusal and the patch-id cases in
  pytest) (unit: gates)
  (test: test_gate_queue_order.py::test_the_queue_runs_the_next_merge_then_the_moved_then_arrival)
  (test: test_gate_carry.py::test_a_git_older_than_2_39_refuses_the_carry_and_says_so);
- Claude cost by CR (one line in the main batch; the levels, the pages, the shares, the Chief of
  Staff's lines, an unpriced model and the audit in pytest); Copilot cost breakdown (`Agent
  <type>` lines) and by CR, estimated calls, updates and failures (unit: parallel) (test:
  test_cost_reading.py::test_the_levels_the_pages_the_pause_and_a_relay) (test:
  test_cost_copilot.py::test_copilot_cost_lists_the_foreman_then_each_agent_type_and_attributes_by_cr)
  (test: test_cost_copilot.py::test_copilot_cost_refuses_what_it_cannot_read);
- a planning surface (its own git repository, two projects, each clone and worktrees outside it,
  run on GitHub in its own unit): a command at the surface exits 2 naming the projects, a
  missing clone fails preflight, init makes the planning folder and its .gitignore; a batch in
  each project at once, a second open on one refused, one seat per project; `take` carries `cli:`
  with `--project`, `clone:` and `archive:` (`not in the PR` for a project that does not set it to `yes`); the
  surface's git lists the CR documents and never a local file (`batch.json`, `events.jsonl`,
  STATUS files, locks, `seat.json`, gate logs), the clone stays clean; `ship` says the archive is
  missing from the PR until it is there; `order merged` writes `delivery.md`; `rules` lists the
  project's instructions then the surface's; `close` archives the CR (unit: surface-board)
  (test: test_external_archive.py::test_an_external_surface_gets_the_planning_folder_and_the_project_stays_clean);
- the surface's writer: a real `serve --seat` on a surface with a bare origin prints its `writer:` line;
  a `file` then `triage` reach the origin within the shortened bound (`CHANTIER_WRITER_TEST_TIMES`);
  `seat` prints `writer: synced`; a commit pushed from a second clone is integrated; a change on both
  sides gives `writer: conflict` and `sync-conflict@1`, and the Chief of Staff's resolution is pushed
  with `sync-resumed@1`; `sync now` commits and pushes the configuration file a save left; with the
  board stopped `file` is refused with "the surface's writer is not running: nothing written" and
  nothing changes; an in-project board has `writer == {"state":"off"}`, no `autosync` key and a
  route of the versions before protocol 1 (`/api/autosync`) answers 404 (unit: surface-board);
- the live terminal view (CR-418): with the real `serve --seat` running over a batch with a working
  CR, `chantier live --once` and `chantier live --once --transport http` each exit 0 with the CR in
  Tasks, the Agents and Ready boxes drawn, a Flow line's date and time, and `working 1` in the
  header, the planning folder's git status and `forge-journal.jsonl`
  unchanged; once the board has stopped, `live --once` exits 4 with `no board runs for this
  surface` (unit: surface-board) (test:
  test_live_link.py::test_live_once_prints_the_working_cr_and_its_lease_and_a_journal_line_comes_once);
- two sessions on one machine (CR-323): `status` and `preflight` list the other batches of the surface (`other batches on this surface: <project> <batch> <state>, steering <who>, <n> Drivers`, P14 informational, passing, and no P14 line in-project); one board per repository: a second `serve --port 0` with a live board prints `board already running at` its link, also from another project of the surface with `--seat`, `GET /api/board` answers its `pid`, `server.json` holds the `server` entry while the board runs and no more once it has stopped, the key staying, and a `board.json` of an older version (a key, a live older `running` record) is migrated into it and deleted, the new board refused with the stop command (unit: surface-board) (test: test_board_running.py::test_a_new_board_reuses_refuses_or_starts_by_what_the_surface_already_runs);
- typed waits (CR-409): `wait add` records a merge, approval, pipeline and answer wait on a CR
  (ids w1..w4, the forge ones on its PR), `status` shows them on the CR's row, the hub tells the
  approval and pipeline waits the forge shows met in one `wait-cleared@1` line each, once
  whatever the cycles, the waits stay open until `wait clear` (needs `--epoch`), and the merge
  wait is told when the PR merges (unit: surface-board); on GitLab, a blocked hand-back with `--wait
  pipeline` records the wait on the head and the MR, the fake `glab` (`api graphql`) turns the head
  green, the hub tells it once and the Foreman clears it and takes the CR back, the approval half
  not played (not proved on GitLab) (unit: gitlab) (test: test_waits.py::test_a_blocked_handback_records_its_waits_and_the_steering_session_clears_them);
- the board's PRs (the `prs.get` op over HTTP, the fake `gh` answering its one `api
  graphql` query): one row per CR with a PR, read on the forge against the record; a PR merged on
  the forge and not recorded says so until `order merged`; a conflicting PR, a draft and a PR whose
  checks the forge has not computed (`being checked`, never `none`) told apart; every PR merged or
  closed is `all_done`, a CR added after brings a new row; the folder (but `forge-journal.jsonl`) and
  its git status unchanged and no call but `api graphql` queries (unit: surface-board);
- the merge the forge signals (CR-303, CR-358): the read that sees a PR merged on the fake forge and
  not in the record leaves one line in `forge-journal.jsonl` (once, `source: board`, ignored by git,
  the only file the page writes); `status` prints `forge saw merged: <cr> <pr> into <branch> at
  <time>; for the Chief of Staff: order merged <cr>`, and so does the Foreman's heartbeat form
  (`status --refresh --batch --epoch`) with the batch's orders unchanged; after `order merged` the
  line no longer prints (unit: surface-board);
- the forge hub and `chantier watch` (CR-358, CR-429), on a two-project surface with the fake `gh`,
  the test seams `CHANTIER_HUB_TEST_TIMES` and `CHANTIER_API_TEST_TIMES` shortening the cycle, the
  quiet and the board's waits, the surface's `chantier.yaml` naming a free `board.port`, the
  watchers background processes and the board a watcher starts killed through `server.json` at the
  step's end:
  - `status` of a running batch with no watcher prints `forge hub: none running` and, as its last
    line, `watch: not running: for the Chief of Staff, start in the background: <command>` (the
    command ends `watch --after 0`, no `--batch`, then `; after the user's no, at each user
    message: <command> watch --once --after 0`); while watchers of the session run, it prints
    `watch: this session's watcher runs; pull path: <command>` and no `not running` line; after a
    watcher's end it ends with the line again; `--after` past the journal's end exits 1, and
    `watch --once` with no `--after` exits 1 (unit: surface-board) (test:
    test_watch_events.py::test_watch_refusals_and_the_pull_path,
    test_forge_hub.py::test_status_and_the_start_line_name_the_journal_the_hub_and_its_version,
    test_watcher_autostart.py::test_the_outputs_end_with_the_line_when_no_watcher_of_this_session_runs);
  - with no board, A's watcher, its session holding A's seat, starts one, detached: its start line
    ends `; started the board (PID <n>)`, the PID `server.json` names, and the board's `board:
    watches the planning files` line follows; B's watcher subscribes to the same board and starts
    none; the `hub` entry of `server.json` names the board's PID, never a watcher's, with a read per
    project; `status` prints `forge hub: PID <board pid>, the surface server, last read <t>`; each
    cycle makes one `api graphql` call per project with an open PR (unit: surface-board) (test:
    test_watch_board.py::test_the_seat_rule_with_and_without_a_running_board,
    test_watch_board.py::test_the_start_is_detached_on_each_system,
    test_watch_board.py::test_the_boards_lines_follow_the_start_line,
    test_forge_hub.py::test_a_hub_cycle_reads_only_what_there_is_to_read_and_is_due_every_twenty_seconds);
  - A's PR merged on the forge: A's watcher ends with `forge saw merged: ... order merged <cr>` and
    `watch: <batch> still running: for the Chief of Staff, start again in the background now:
    <command> watch --after 1`, the merge written once (`source: hub`); B's watcher keeps running
    and the board keeps reading the forge; neither project's record changes (unit: surface-board)
    (test: test_forge_hub.py::test_a_hub_cycle_writes_each_event_once,
    test_watch_events.py::test_a_watcher_ends_twenty_seconds_after_the_last_line_that_wakes);
  - two of A's merges within the quiet give one end with both lines, for a `--for role:griller`
    watcher too; a watcher restarted with `--after <n>` subscribes, starts no board and replays
    nothing (unit: surface-board) (test:
    test_watch_events.py::test_a_watcher_ends_twenty_seconds_after_the_last_line_that_wakes,
    test_watch_board.py::test_a_lost_link_is_opened_again_from_the_cursor_and_repeats_no_line);
  - a ready PR's checks failing print `forge saw checks red` at the watcher's end and never in
    `status` (unit: surface-board) (test:
    test_forge_hub.py::test_status_and_the_start_line_name_the_journal_the_hub_and_its_version);
  - `order merged <cr>` twice: the second answers `<cr> already merged` (unit: surface-board);
  - with every watcher ended and no page open, the board still runs, its `hub` entry says `idle`,
    `status` prints `forge hub: PID <n>, the surface server, idle (no client subscribed)` and the
    fake `gh` is called no more (unit: surface-board) (test:
    test_board_idle.py::test_the_hub_reads_the_forge_only_while_a_client_observes,
    test_forge_hub.py::test_the_hub_line_names_the_surface_server_and_says_idle_while_no_client_is_subscribed);
  - a merge the board's PRs page reads first: the page writes the line (`source: board`), a watcher
    wakes on it, and the hub, observed again, reads the forge at once and writes no second line
    (unit: surface-board) (test: test_forge_hub.py::test_the_board_and_the_hub_share_the_journal_once,
    test_board_idle.py::test_a_client_observes_with_a_socket_sub_or_a_recent_long_poll);
  - A's batch paused (every CR merged or dropped): A's watcher keeps running, and `status` still
    holds the `pull path` line; a board write on A (`new`) ends it with the `board wrote (new)`
    line and the restart of its batch; `watch --once --after 5` prints the same line, then
    `watch: cursor 6; next, at the user's next message: <command> watch --once --after 6`, and
    takes no lock; a board write on the other project does not end A's watcher and lands in that
    project's journal only; another session's `seat take` ends A's watcher with `watch: the seat of
    demo is another session's now; ended`, and the board A's watcher started, which follows that
    seat, stops (unit: surface-board) (test:
    test_watch_events.py::test_watch_refusals_and_the_pull_path,
    test_watch_events.py::test_the_pull_path_prints_the_lines_past_the_cursor_and_takes_no_lock,
    test_watch_events.py::test_the_seat_of_another_session_ends_the_watcher_with_its_line,
    test_watch_events.py::test_the_board_and_config_lines_are_never_duplicates_and_status_holds_none);
  - a watcher of a project with no seat and no board ends with `watch: no seat for <project>, so no
    board started; ended: ...`, exit 1, and starts no board (unit: surface-board) (test:
    test_watch_board.py::test_the_seat_rule_with_and_without_a_running_board);
  - a board started by hand with `--forge-always`: a watcher of a project with no seat subscribes to
    it; a journal of version 0 lines is kept as written; with no client subscribed the hub still
    calls the fake `gh` each cycle; a PR merged after A's pause writes no line for A and the hub no
    longer reads its PRs; the other project's merge is written once by the hub and `watch --once
    --after 2` prints it (unit: surface-board) (test:
    test_board_idle.py::test_with_the_forge_always_the_hub_reads_with_no_client,
    test_board_idle.py::test_the_two_flags_together_are_a_usage_error);
  - the journal is ignored by git (`git check-ignore`), the record (`batch.json`, `events.jsonl`)
    is unchanged by the hub, a forge error lands in the `hub` entry and not in the journal, and no `gh`
    call is made but read-only `api graphql` queries (unit: surface-board) (test:
    test_forge_hub.py::test_a_forge_error_lands_in_the_hub_record_not_in_the_journal,
    test_surface_server.py::test_a_hub_entry_that_cannot_be_written_is_written_at_the_next_cycle);
  - an outside poller (CR-410): two CRs name one Jira link on their `issue:` lines (one in the inbox,
    one triaged to `2-backlog/P2/`); `interests --kind issue --json` lists the link twice
    (`tracker` `jira`, `read_by` `outside`, exit 0); a board started by hand and a watcher
    subscribed to it, `journal add issue@1 --json -` with the payload on stdin writes `journal: seq
    <n> issue@1 commented on <link> (<folders>)` and the watcher ends on `tracker saw commented on
    <link> (<folders>): "<text>"; for the Chief of Staff: tell the user in one line, record
    nothing`; the same add again says `journal: already there (seq <n>)`; a ref no CR names (exit
    2), a payload with a `cr` key (exit 1) and the type `merged@1` (exit 2) are refused, the journal
    unchanged each time; the fake `gh` is never called (unit: surface-board) (test:
    test_outside_poller.py::test_journal_add_writes_the_event_once,
    test_outside_poller.py::test_journal_add_refuses_what_it_must_and_writes_nothing,
    test_forge_hub.py::test_the_hub_never_collects_the_issues_provider);
  - `serve` and `webui` (CR-456, unit: surface-board): a second surface's `serve` on a default port the first holds
    takes a free port and prints `board: port ... takes port <n>`, each server answers with its own cookie
    only; `webui` on a running server prints `board already running at`; after the server is killed it starts
    `serve --stop-idle` with no `--seat`, prints `board on` and the idle-stop line, and the server answers
    `board.get`; a watcher's board still runs `serve --seat ... --stop-idle`;
  - remote commands (CR-458, unit: surface-board): `login <private link>` stores the profile for the served project and prints
    no key; through it a `file` lands in the server's inbox, a `note` shows in the record, and a `status` prints what
    `status --profile local` prints less the `watch:` line; `gate` is refused (exit 1); `login <read link> --profile ro
    --no-default` then a `note --profile ro` is refused with nothing written; `logout` ends the profiles; with the server
    stopped and a profile set, a remote `status` exits 4 with its `error: remote:` line and a command for another
    project still runs here;
  - the surface server (CR-386, CR-429), on the same surface: `chantier serve --port 0` started by
    hand prints `board: watches the planning files`, `server.json` names its PID in `server` and in
    `hub` with its file watch, `status` prints `forge hub: PID <board pid>, the surface server, idle
    (no client subscribed)`, and no `board.json` or `hub.json` is left; a `project` subscription
    over a WebSocket gets an event for a CR filed by the CLI, and a `backlog.move` over HTTP reaches
    it as an event with a new `rev` within 3 s; a second `serve --port 0` prints `board already
    running at`, also with `--seat` from the other project; a `board.json` prepared with a key and a
    live older `running` record refuses `board` with the stop command and its key lands in
    `server.json`; a watcher of A started while the board runs subscribes, starts no board, and ends
    on A's merge with `forge saw merged: ... order merged <cr>`, the line written once with
    `source: "hub"`; the board killed hard, the running watcher starts a new one, `status` names the
    new PID with a `last read`, and the next merge still wakes it; the board a watcher started
    outlives the watcher and stops once its seat is released; a watcher with no event ends with
    `watch: no event for <name> in 2 h; ended, ...`, then its board stops by itself with no
    subscriber, its writer's final cycle having pushed the CR filed just before; the record is
    unchanged by the server and the git folder's `chantier/` holds only `server.json`,
    `server.json.lock`, `hub.lock`, `writer.lock`, `writer.wake` and the
    `watch-<project>/<session>.lock` files (unit: surface-board) (test:
    test_board_idle.py::test_the_start_line_says_the_file_watch,
    test_file_watch.py::test_the_push_loop_walks_nothing_per_pass_and_one_settle_moves_the_topics,
    test_file_watch.py::test_the_notification_backend_sees_a_write,
    test_board_idle.py::test_an_idle_board_stops_and_its_writer_runs_before_its_entry_goes,
    test_watch_board.py::test_a_watcher_with_no_event_that_wakes_ends_after_the_idle_end,
    test_watch_board.py::test_a_refusal_a_silent_board_or_a_board_gone_ends_the_watcher,
    test_surface_server.py::test_two_writers_of_server_json_lose_neither_entry,
    test_board_running.py::test_new_key_keeps_the_running_record_and_the_exit_removes_only_its_own);
- the two limits `specifying.parallel` and `batch.slots` (CR-383): the board's `config.put` op writes
  the project folder's file and says, role-free, `slots 4 -> 6: <batch> keeps <n> until an order
  slots` and `specifying 4 -> 1: from the next start`, with no `applies at the next batch` line;
  each save writes one `config@1` line per changed key in the forge journal (`source: board`; a role's
  model too, keyed `hosts.<host>.roles.<role>.model`) and a running `chantier watch` ends on it with the `config changed on the board` line; `status` prints the slots line once
  and the specifying one never, and no longer after an `order slots`; with `specifying.parallel` 1
  and a `work/specifying` marker, `playbook` prints `limits:` with `[surface project]`, `markers 1
  (<slug>)` and `specifying at the limit`; `open` with no `--slots` takes the project folder's
  `batch.slots` and names `[surface project]` (unit: surface-board) (test:
  test_limits.py::test_the_board_saves_a_limit_keeps_comments_journals_one_line_and_removes_it,
  test_limits.py::test_a_put_of_both_limits_and_a_role_edit_writes_three_lines_and_status_follows_the_orders,
  test_limits.py::test_open_and_the_playbook_take_the_limits_from_the_layers,
  test_forge_hub.py::test_a_config_line_ends_the_watcher_and_is_told_in_its_form,
  test_board_config.py::test_a_save_writes_one_config_line_per_changed_key_and_a_dry_run_none);
- addressed events (CR-385): every line of `forge-journal.jsonl` the hub and the board write is
  version 2, `v`, `seq`, `t`, `type`, `source` and `audience: ["project"]` first, with no `by`; a
  journal of version 0 lines (a `by`, no `v`) keeps them as written, a board write appends its
  version 2 line after them and the watcher started with the printed `--after` prints it once; a
  default watcher and one started with `--for role:griller` (its start line lists `for project,
  ... role:griller`) both end on a forge merge, which is for the project; with `events.wake_every:
  2m` in the surface project's `chantier.yaml`, `playbook` prints `events: wake every 2m [surface
  project]` after the limits (the shipped `20s` with no label) (unit: surface-board) (test:
  test_event_audience.py::test_an_append_writes_a_version_two_line_for_the_project,
  test_event_audience.py::test_a_version_zero_line_reads_as_the_projects_and_a_newer_one_wakes_no_one,
  test_event_audience.py::test_a_watcher_ends_on_the_lines_for_it_and_passes_the_others,
  test_event_audience.py::test_playbook_prints_the_wake_rule_with_its_layer);
- the board's backlog writes (the `backlog.move` op, a refused one): each write that changes something
  appends one `board@1` line to the project's `forge-journal.jsonl` (`source: board`, `wakes` true for a
  move, ignored by git), a refused one none (unit: surface-board) (test:
  test_board_journal.py::test_each_backlog_write_adds_one_board_line_to_its_projects_forge_journal,
  test_board_journal.py::test_a_refusal_a_rescan_and_another_project_leave_no_line_here);
- the board's running-batch lane (CR-427; the scenario's batch is open): `backlog.move` to
  `running-batch` of a backlog CR carrying `work/specifying` writes `work/running-batch` naming the
  batch and moves no folder, appends one `board@1` line with the action `running-batch`, shows the
  item with `running_batch: <batch>` in `project.state` and on `status`'s `running batch:` line; a
  grilled CR whose spec-writer has not started is refused (409, `the grill is not finished`) and
  writes nothing; the marked CR moved back to `P2` loses its mark. The no-open-batch drop has no
  step here: its cover is the in-process test (unit: surface-board) (test:
  test_board_running_lane.py::test_a_drop_that_marks_nothing);
- the server's API, protocol 1 (CR-406), against the real `chantier serve` process, its times
  shortened by `CHANTIER_API_TEST_TIMES` (`1:6:5:5`), through `websockets.sync.client` and `http.client`:
  a WebSocket with the cookie from the board's own origin gets `welcome` (the 27 ops, the 8 topics,
  the probe's PID); a `project` subscription gets its event, then `chantier file` run as a command in
  the same project makes an event with a new rev within the push loop's look plus 2 s;
  `backlog.move` over the socket moves the folder and writes one `board@1` line, which an `events`
  subscription receives; over HTTP `board.get`, a write (`backlog.move`) and a long-poll that answers
  when `chantier file` runs; the cookie from a foreign origin answers 401 on HTTP and on the upgrade,
  the key in a header from a foreign origin is accepted on both; a `hello` with a wrong key gets an
  `error` frame and the close code 4401; `GET /api/board` holds the probe's six fields and
  `protocols: [1]`; a route of the versions before protocol 1 answers 404, a `POST` with the cookie
  too; the board stopped closes the open socket with 1001; the cases that read the board
  (`remote_board`'s state, tree, file and costs checks and its seat count, `forge_hub`'s PRs read and
  write, `external_surface`'s two projects and refused paths, `surface_config_page`'s `config.get` and
  `config.put`) call the ops over `/api/v1/call/<op>` (unit: surface-board) (test:
  test_server_api.py::test_the_key_and_the_origin,
  test_server_api.py::test_an_old_route_answers_404_even_for_a_post_a_cookie_carries,
  test_server_api_ws.py::test_a_socket_says_hello_gets_welcome_and_watches_a_project,
  test_server_api_ws.py::test_a_stopping_server_closes_each_socket_with_1001);
- the board's exposure (CR-426): `serve --port 0` with no `--host` and no `chantier.yaml` listens on
  127.0.0.1 (`server.json` records it, one start line); with `board.host: network` it accepts either
  outcome, as the runner's network decides: the link on a network address (`server.json` records
  0.0.0.0, then the `on this machine:` link, then the `board: listens on the local network (` line),
  or the link on 127.0.0.1 and the `board: no local network address found; on this machine only` line;
  `board.host: 127.0.0.1` in `chantier.yaml` is refused by `playbook` and `board` (exit 2) with the
  message pointing to `--host`; a second `serve --new-key` on a running board prints another key, the
  first link answers 401 and the new one 303 with `Max-Age=2592000` (unit: surface-board) (test:
  test_board_exposure.py::test_the_default_is_this_machine_and_network_is_found_at_each_start);
- the board's UI folder (CR-411): `serve --ui <folder>` serves that folder's `index.html` with the
  policy and its `app.js`, and none of the shipped client's files; `--ui none` answers the 404 line
  outside `/api/` while `board.get` answers over HTTP; a folder with no `index.html` is refused
  with the usage exit (1) and records no board entry; `--ui` on a running board prints the `--ui not applied` line,
  exits 0, and leaves the shipped client served (unit: surface-board) (test:
  test_board_ui.py::test_a_folder_is_served_by_its_files_and_types_inside_it_only,
  test_board_ui.py::test_with_no_ui_the_page_is_a_404_line_and_the_api_answers,
  test_board_ui.py::test_a_ui_that_is_not_a_folder_with_an_index_is_refused_and_nothing_is_written,
  test_board_ui.py::test_ui_on_a_board_already_running_is_not_applied_and_said);
- prepared-CR filing, lifecycle moves, collisions and rollback: `triage` between the inbox, the
  backlog and `3-ready`, a failed `open` restoring what it moved, `restore`, the next batch
  number read from the records (unit: series-deps, qa-driver) (test:
  test_triage_moves.py::test_triage_moves_between_the_folders_and_refuses_what_is_not_a_move)
  (test: test_opening_and_restore.py::test_an_opening_that_fails_names_why_and_restores_what_it_moved)
  (test: test_opening_and_restore.py::test_restore_puts_a_trashed_cr_back_whole_and_refuses_a_clash_or_an_archive);
- a release: added to a running batch (`order add --release`) it waits for each other CR, a
  later one too, with no confirmation of the version; in a stack or a series it starts on the top
  CR's branch once every other CR is ready and stacked (refused before, naming the CR and its
  head), its PR the top of the stack, `ready` and not blocked while it waits for its merge; in a
  parallel batch it starts once the others are merged; `order add` refused once it has started,
  `--fix-for` accepted; `order merged` and `order confirm` refused while another CR is open; an
  irreversible action refused until the release PR is merged (an approval never covers it), then
  `go` because of the merge, with no approval; a procedure with no release PR, whose go is the
  user's word (`order confirm`); a change of content under a prepared release; a fix CR that stops every `go` until it merges and a new attempt, and
  a grant (the Foreman merging the fix and the release PR with the forge's CLI after `release
  go`, recorded with `order merged --epoch`; a merge the forge refuses; the budget; the number of
  releases); an approval recorded while the release PR waits for its merge takes no Driver, is
  not spent by a merge under the grant, and the Driver started at the merge sees it (`approvals
  unused:`); a `wait:` note recorded right after the merge leaves the take at the merge reading
  `merged:`; a publication refused by the host and done by the user: the release `blocked
  approval: publish:` goes back to a Driver on the steering session's `order note ... "publication
  done: ..."`, with no new attempt, and ends `3-done` (unit: release);
- the event log, and the forge's call log: only the agents called it (unit: parallel);
- a paused batch: `pause` printing the cost to date (the whole summary, not cut), recorded with a
  to-date line and one total in `STATUS.md`, a second `pause` refused, `order add` leaving it
  paused, `take` setting it running again, `close` on a running batch saying `pause` comes first,
  a call made after `pause` counted (unit: parallel) (test:
  test_cost_reading.py::test_the_levels_the_pages_the_pause_and_a_relay);
- closing on the user's word: `close` refusing, with and without `--yes`, a CR not merged, an
  open order, a stack agent, a Foreman whose last call waits on a tool (its file aged 10
  minutes), a held agent (a CR's or a QA order's `agent`) whose last record is a tool's result
  or whose last line is cut JSON, a held id with no transcript (cleared by `agents set <cr> -`),
  the current Foreman of two recorded, a missing Foreman transcript, and, on a Copilot batch, a held
  agent whose lease is live or that has no lease (`not measured (no lease)`), passing once its
  lease is not confirmed; passing an agent that handed back
  or ended its turn though its file was just written; passing, with the unrecorded subagents
  that run or cannot be read (and a held Driver's own subagent, an earlier Foreman's main
  transcript) listed apart under a heading and never judged, ended ones not listed; `--stopped`
  passing a held running agent on its stem or its bare id (writing nothing without `--yes`), the
  current Foreman's session id, refused for a subagent the batch does not hold, an earlier
  Foreman's session id, an unknown name, an ended agent, a transcript that cannot be read and the
  stack agent, and never past another held running agent or a record cause; a
  pricing failure refused the same way; the declaration kept in the record
  (`stopped_agents`), under Cost in `batch-NN.md` and in what `close --yes` prints, and absent
  from a record closed without the flag; a reopened batch named as such; then the final cost
  printed (with a call made after the last `pause`) and the folder deleted by `close --yes`, the
  dropped CR's worktree and branch by the Chief of Staff's git (unit: parallel);
- the batch's record: `open` writes `5-archives/batches/batch-NN.json` as running; `close` names
  the record and the retro's destination, touching nothing without `--yes`, on an archive
  collision or on a planted `batch-NN.md` (exit 3, all put back); then the closed JSON (cost,
  CRs, archives) and the Markdown (table, cost, the retro byte for byte), no `retro.md` in any
  CR archive, the records neither listed nor counted on the board; no retro printing `retro: no
  retro`; `status`'s `last closed` line and the no-batch refusal's tail; the next number read
  from the records (unit: parallel) (test:
  test_opening_and_restore.py::test_the_next_batch_number_is_read_from_the_records);
- in external mode, the batch's records in the surface, never in the CR's PR archive (unit:
  surface-board);
- `chantier validate` on a planning folder with eleven filed CRs and no summary: exit 0, the counts
  line first, every gap printed (more than ten lines), each `no summary` line the matching
  `summary lint` line behind `gap `; on a closed batch's surface (archives with `delivery.md`,
  the batches' records) exit 0 and no `error` line; its findings and refusals (unit: surface-board)
  (test: test_validate.py::test_what_chantier_misreads_is_an_error_and_exits_3).

## Adding a case

A new check goes in one of two places, and nowhere else.

- It joins a case of an existing unit, or a new case in that unit's list in `UNITS`, when it
  needs a batch to run: a scripted Foreman or Driver, a forge, a worktree, a close. Read the
  unit's budget: a case that pushes a unit over it only warns, but the budget is what keeps the
  whole run short, so the unit's literal is edited with the case.
- It goes to pytest, in `skills/chantier/scripts/cli/tests/`, when it is a refusal or a figure
  the CLI gives on a prepared state: write the state (a `batch.json` edited, a transcript on
  disk), call the CLI in-process with the `chantier` fixture, parametrize, and keep `just test`
  within its budget (see AGENTS.md).

Never a new unit without the user's word: a unit is a new process and a new world, and its
budget joins the wall time. A unit over its budget warns and only a hung unit fails.

Every new check maps to its bullet in the coverage list above, with `(unit: <name>)` or `(test:
<file>::<test>)`; `test_scenario_coverage.py` fails when a bullet names a unit or a test that
does not exist. Add a bullet when the check is a new behaviour.
