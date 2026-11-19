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

Measured on 2026-11-15 on a Windows 11 machine (Ryzen 7 7800X3D, 16 logical cores), with other
chantier sessions running their own scenario runs on it, so the machine was heavily loaded and not
quiet; all checks passing in every run.

The budget of the `stack` unit (640 s) follows this README's own rule, the loaded `--jobs 4` time plus
about 25 percent, from 510.8 s. Its solo time (`--unit stack`) is well under it: three runs after the fix
took 264.4 and 277.5 s on a lightly loaded machine (about 265 to 280 s) and 381.0 s on a heavily loaded
one (129 of 129 checks each), against 318.7 s before the fix. Two full runs with `--jobs 4`, under a
heavier load than the first table of this section had:

| unit | budget (s) | run A (s) | run B (s) |
| --- | ---: | ---: | ---: |
| parallel | 260 | 274.7 | 245.1 |
| stack | 640 | 440.2 | 510.8 |
| release | 420 | 410.8 | 429.9 |
| gates | 400 | 381.0 | 392.1 |
| series-deps | 260 | 331.7 | 327.9 |
| direct | 125 | 149.9 | 120.6 |
| surface-board | 300 | 236.3 | 196.0 |
| qa-driver | 115 | 166.0 | 131.9 |
| gitlab | 95 | 92.0 | 67.5 |
| wall time | | 606.2 | 642.7 |
| sum of the units | | 2254.5 | 2421.8 |

Under a full `--jobs 4` run on a loaded machine every unit is slower, since the processes compete
for the same disk and CPU (`stack` took 440 to 511 s), and a unit over its budget only raises a
warning. The `--jobs 8` rows of the earlier table predate the fix and were not re-measured. The
target of under 300 s on a quiet machine and on Linux CI is not proven: no run came under 300 s
except the solo `stack` runs, and a quiet Linux machine, where a process starts much faster than on
Windows, has to confirm it and lower the budgets.

In a unit, a scripted Foreman reads the batch's state and does what its card leaves it (fills the
slots, asks, merges what the user allowed, cleans up, pauses); scripted Drivers create their
worktree, commit, rebase, push and open their PRs against the fake forge, and use the CLI for
its record (`round`, `gate`, `ship`, `handback`); the Chief of Staff steers with `chantier
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
  (uncommitted changes, a head not pushed, no long gate at it), a QA ordered during the batch,
  with its folder in the inbox, that holds no CR back and keeps the batch from pausing until done;
  its refusals (no request, a spent budget, its folder not opened) in pytest (unit: parallel,
  gates, qa-driver) (test:
  test_rail_refusals.py::test_order_qa_needs_a_request_and_a_budget_and_its_folder_is_not_opened);
- `verdict VERIFIED` refused without `work/verify.md` naming the head (no file, a stale `Head:`),
  `NOT VERIFIED` accepted without it (unit: gates)
  (test: test_verdict_note.py::test_verified_needs_a_verify_note_naming_the_head);
- the step a working CR is at: `round` recording `coder r1`, `phase` recording the inspector, a
  gate with its detail, `ci`, in the CR's STATUS.json, the batch row, `chantier status` and
  STATUS.md, the `phase` event outside the Progress steps, the step cleared by `handback` and
  `take`; the read data of the board naming `phase` and `next_to_start` (none with the budget
  spent); `phase` refusing a queued CR, a `review` with no detail and a detail
  past 40 characters in pytest (unit: parallel, surface-board) (test:
  test_rail_refusals.py::test_phase_refuses_a_queued_cr_a_review_with_no_detail_and_a_long_detail);
- dropping a live CR (its processes stopped), adding an item, an order applied at once and
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
- a stack (`open --mode stack`) of independent CRs: all taken at once, each started on the
  default branch, then stacked afterwards by `stack` (`ship` records the default branch before,
  the CR under it after); a CR starting on the nearest earlier CR with a PR (a working one too; a branch with no PR, a
  cancelled or merged CR skipped; a fix, a release, a CR with an `after` and a parallel batch
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
  `ship` reading the draft state from the forge, the hand-back line by word (for `PR in draft`, its PR's draft state and the CR (and PR) it waits
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
- a batch opened with no CR, born paused and a factory (`factory: true`, the brief's `Factory: on.`,
  `status` saying `factory: on` and `no CR yet`), then a factory batch in a direct batch:
  `triage --ready` joining it in the same call (queued, still paused, one `add` order with its
  `origin`), the last CR's end pausing it with the factory `next:` line and no close offered,
  `order factory off` saying the retro comes next, `close` refused only for the cost of a batch no
  transcript steered (unit: direct) (test:
  test_factory.py::test_triage_ready_joins_a_factory_batch_on_its_own);
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
- a surface that names an autosync (`scenario/fake_autosync.py` stands for the surface's script):
  no P13 or status line without the mention, script missing, no group yet, then active (with and
  without a live participant, a dead participant's file kept), stopped, blocked and approval,
  each with its exact two lines; the board's join argv and the group naming the board; `GET
  /api/autosync`, `start` refused while blocked, `stop` refused while stopped, a stale incident
  refused, an approval that runs `approve` then `start`; an in-project board has no autosync
  (unit: surface-board);
- two sessions on one machine (CR-323): `status` and `preflight` list the other batches of the surface (`other batches on this surface: <project> <batch> <state>, steering <who>, <n> Drivers`, P14 informational, passing, and no P14 line in-project); one board per repository: a second `board --port 0` with a live board prints `board already running at` its link, also from another project of the surface with `--seat`, `/api/board` answers its `pid`, `server.json` holds the `server` entry while the board runs and no more once it has stopped, the key staying, and a `board.json` of an older version (a key, a live older `running` record) is migrated into it and deleted, the new board refused with the stop command (unit: surface-board) (test: test_board_running.py::test_a_new_board_reuses_refuses_or_starts_by_what_the_surface_already_runs);
- the board's PRs page (`GET /api/projects/<id>/prs`, the fake `gh` answering its one `api
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
- the forge hub and `chantier watch` (CR-358), on a two-project surface with the fake `gh`, the
  test seam `CHANTIER_HUB_TEST_TIMES` shortening the cycle and the quiet, the watchers background
  processes:
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
  - project A's watcher takes the hub lock (`, the hub`), project B's is not the hub, the `hub`
    entry of `server.json` names one PID and a read per project, `status` names that PID
    (`a watcher`), and each cycle makes one `api graphql` call per project with an open PR, never
    two hubs' worth (unit: surface-board) (test:
    test_surface_server.py::test_one_watcher_holds_the_hub_lock_and_the_next_takes_it,
    test_forge_hub.py::test_a_hub_cycle_reads_only_what_there_is_to_read_and_is_due_every_twenty_seconds);
  - A's PR merged on the forge: A's watcher ends with `forge saw merged: ... order merged <cr>` and
    `watch: <batch> still running: for the Chief of Staff, start again in the background now:
    <command> watch --after 1`, the merge written once (`by: hub`); B's watcher keeps running,
    takes the lock and the next cycles still read the forge (unit: surface-board) (test:
    test_forge_hub.py::test_a_hub_cycle_writes_each_event_once,
    test_watch_events.py::test_a_watcher_ends_twenty_seconds_after_the_last_line_that_wakes);
  - two of A's merges within the quiet give one end with both lines; a watcher restarted with
    `--after <n>` replays nothing (unit: surface-board) (test:
    test_watch_events.py::test_a_watcher_ends_twenty_seconds_after_the_last_line_that_wakes);
  - a ready PR's checks failing print `forge saw checks red` at the watcher's end and never in
    `status` (unit: surface-board) (test:
    test_forge_hub.py::test_status_and_the_start_line_name_the_journal_the_hub_and_its_version);
  - `order merged <cr>` twice: the second answers `<cr> already merged` (unit: surface-board);
  - a merge the board's PRs page reads first: the page writes the line (`by: board`), the hub's
    reads of it write no second line and the watcher wakes on the board's line (unit:
    surface-board) (test: test_forge_hub.py::test_the_board_and_the_hub_share_the_journal_once);
  - A's batch paused (every CR merged or dropped): A's watcher keeps running, and `status` still
    holds the `pull path` line; a board write on A (`new`) ends it with the `board wrote (new)`
    line and the restart of its batch; `watch --once --after 5` prints the same line, then
    `watch: cursor 6; next, at the user's next message: <command> watch --once --after 6`, and
    takes no lock; a board write on the other project does not end A's watcher and lands in that
    project's journal only; another session's `seat take` ends A's watcher with `watch: the seat of
    demo is another session's now; ended`; a PR merged then writes no line for A and the hub reads
    none of its PRs (unit: surface-board) (test:
    test_watch_events.py::test_watch_refusals_and_the_pull_path,
    test_watch_events.py::test_the_pull_path_prints_the_lines_past_the_cursor_and_takes_no_lock,
    test_watch_events.py::test_the_seat_of_another_session_ends_the_watcher_with_its_line,
    test_watch_events.py::test_the_board_and_config_lines_are_never_duplicates_and_status_holds_none);
  - the journal is ignored by git (`git check-ignore`), the record (`batch.json`, `events.jsonl`)
    is unchanged by the hub, a forge error lands in the `hub` entry and not in the journal, and no `gh`
    call is made but read-only `api graphql` queries (unit: surface-board) (test:
    test_forge_hub.py::test_a_forge_error_lands_in_the_hub_record_not_in_the_journal,
    test_surface_server.py::test_a_hub_entry_that_cannot_be_written_is_written_at_the_next_cycle);
  - the surface server (CR-386), on the same surface: `chantier board --port 0` runs in the
    background, `server.json` names its PID in `server` and, within one cycle, in `hub`, `status`
    prints `forge hub: PID <board pid>, the surface server, ...`, and no `board.json` or `hub.json`
    is left; a second `board --port 0` prints `board already running at`, also with `--seat` from
    the other project; a `board.json` prepared with a key and a live older `running` record
    refuses `board` with the stop command and its key lands in `server.json`; a watcher of A
    started while the board runs has no `, the hub` and ends on A's merge with `forge saw merged:
    ... order merged <cr>`, the line written once with `source: "hub"`; a watcher that was the hub
    when the board starts yields (`status` names the server's PID within one cycle, one `api
    graphql` per project per cycle); the board killed hard, a running watcher takes the lock at its
    next poll, `status` prints `forge hub: PID <watcher pid>, a watcher, ...` and the next merge
    still wakes it; the record is unchanged by the server and the git folder's `chantier/` holds
    only `server.json`, `server.json.lock`, `hub.lock` and the `watch-<project>/<session>.lock`
    files (unit: surface-board) (test:
    test_surface_server.py::test_the_servers_hub_loop_elects_cycles_when_due_and_lets_go,
    test_surface_server.py::test_two_writers_of_server_json_lose_neither_entry,
    test_board_running.py::test_new_key_keeps_the_running_record_and_the_exit_removes_only_its_own);
- the two limits `specifying.parallel` and `batch.slots` (CR-383): the board's `PUT /config` writes
  the project folder's file and says, role-free, `slots 4 -> 6: <batch> keeps <n> until an order
  slots` and `specifying 4 -> 1: from the next start`, with no `applies at the next batch` line;
  each save writes one `config` line per changed key in the forge journal (`source: board`; a role's
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
  version 1, `v`, `seq`, `t`, `kind`, `source` and `audience: ["project"]` first, with no `by`; a
  journal of version 0 lines (a `by`, no `v`) keeps them as written, a board write appends its
  version 1 line after them and the watcher started with the printed `--after` prints it once; a
  default watcher and one started with `--for role:griller` (its start line lists `for project,
  ... role:griller`) both end on a forge merge, which is for the project; with `events.wake_every:
  2m` in the surface project's `chantier.yaml`, `playbook` prints `events: wake every 2m [surface
  project]` after the limits (the shipped `20s` with no label) (unit: surface-board) (test:
  test_event_audience.py::test_an_append_writes_a_version_one_line_for_the_project,
  test_event_audience.py::test_a_version_zero_line_reads_as_the_projects_and_a_newer_one_wakes_no_one,
  test_event_audience.py::test_a_watcher_ends_on_the_lines_for_it_and_passes_the_others,
  test_event_audience.py::test_playbook_prints_the_wake_rule_with_its_layer);
- the board's backlog writes (`POST backlog/move`, a refused one): each write that changes something
  appends one `board` line to the project's `forge-journal.jsonl` (`source: board`, `wakes` true for a
  move, ignored by git), a refused one none (unit: surface-board) (test:
  test_board_journal.py::test_each_backlog_write_adds_one_board_line_to_its_projects_forge_journal,
  test_board_journal.py::test_a_refusal_a_rescan_and_another_project_leave_no_line_here);
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
  the current Foreman of two recorded, a missing Foreman transcript, and a Copilot session file
  written in the last 5 minutes or whose time is not measured; passing an agent that handed back
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
