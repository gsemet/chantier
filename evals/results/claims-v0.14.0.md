# Claims of v0.14.0

Since v0.13.0, at 18b251d (origin/main). Runs: none.

No eval campaign ran for v0.14.0 (the user's word, 2026-11-19). A claim that a named check of `just scenario` or `just test` proves is `scenario only`; every other claim is `not exercised`. No claim is `exercised`.

| Claim | Commit | Rail | Can come up in | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| One elected surface server for the board and the forge hub | 18b251d7 | none: no row for the surface server; its election has no run on Windows | no campaign | scenario only | test_surface_server.py::test_one_watcher_holds_the_hub_lock_and_the_next_takes_it and ::test_the_servers_hub_loop_elects_cycles_when_due_and_lets_go; run_scenario.py, the surface-board unit |
| Addressed events, one typed journal that says whom to wake | 2702b726 | none: no row for the event journal | no campaign | scenario only | test_event_audience.py::test_a_watcher_ends_on_the_lines_for_it_and_passes_the_others and ::test_the_rate_limit_keeps_a_watcher_up_for_wake_every_and_the_shipped_value_changes_nothing |
| The watcher wakes the session on what the user does in the board | 0571330d | none: no row for the watcher; the session's wake needs a real host | no campaign | scenario only | test_watch_events.py::test_the_board_and_config_lines_are_never_duplicates_and_status_holds_none; test_board_journal.py::test_each_backlog_write_adds_one_board_line_to_its_projects_forge_journal (the journal and the watcher, not a session's wake) |
| Expect the watcher's restart line in the surface-board scenario | 7f1a2916 | none: a scenario step | no campaign | scenario only | run_scenario.py, the surface-board unit |
| Set the specifying limit and a new batch's slots from the board | a033d8a0 | none: no row for the configuration page | no campaign | scenario only | test_limits_cells.py::test_the_board_saves_zero_slots_and_journals_it_and_open_then_refuses; test_playbook_layers.py |
| Show the spend's age, the carried verdict and the draft wording | b47a6c80 | none: the pane and the board's page, no run draws them | no campaign | scenario only | test_cli_units.py::test_a_ready_handback_shows_its_carried_verdict_as_a_step and ::test_the_now_line_of_a_pr_in_draft_takes_the_ready_lines_clause (the text, not the pane drawn in a real session) |
| Check a whole planning folder with chantier validate | cb3ec500 | none: no row for validate | no campaign | scenario only | test_validate.py::test_a_planning_folder_made_by_the_cli_validates_and_nothing_is_written and ::test_what_chantier_misreads_is_an_error_and_exits_3; run_scenario.py |
| A release is finished after the user publishes it by hand | a9fef3fa | C11 | full, claude-planted | scenario only | run_scenario.py, the release unit (the forge check and the end checklist, not a real publication) |
| Stop the hand-started board before the scenario steps that expect none live | 4da09d45 | none: a scenario step | no campaign | scenario only | run_scenario.py, the surface-board unit |
| A board started by hand serves until it is stopped by hand | 4f4605e9 | none: no row for the board | no campaign | scenario only | test_board_running.py::test_a_new_board_reuses_refuses_or_starts_by_what_the_surface_already_runs; run_scenario.py, the surface-board unit |
| Say when the session's watcher is not running | 2cc7c9d2 | none: no row for the watcher | no campaign | scenario only | test_watcher_step.py::test_the_chief_of_staff_cards_carry_the_watcher_step; test_watcher_autostart.py; run_scenario.py |
| The eval audit accepts the QA driver's first line and audits it as a Driver | 8e1f7618 | J1 | full, real-foreman, real-direct, claude-planted | not exercised |  |
| Factory mode: a CR made ready with triage joins the open batch on its own | 958ac5a6 | none: no row for factory mode | no campaign | scenario only | test_factory.py::test_triage_ready_joins_a_factory_batch_on_its_own and ::test_a_release_joining_turns_the_factory_off; run_scenario.py |
| Read only the batch's own status line in the empty-batch scenario leg | e5c1f027 | none: a scenario step | no campaign | scenario only | run_scenario.py, the empty-batch leg |
| Open a batch with no CR, born paused, waiting for its first CR | ba4b9927 | none: no row for the empty batch | no campaign | scenario only | test_open_empty_batch.py::test_open_with_no_cr_is_born_paused and ::test_an_order_joins_the_empty_batch_and_the_first_take_sets_it_running |
| Ask the post-merge word with the merge go | 3a9afc2c | C11 | full, claude-planted | scenario only | test_rail_refusals.py::test_the_release_prs_merge_go_depends_on_the_grant_alone_and_spends_no_approval; run_scenario.py, the release unit |
| A release CR's merged PR stays shown in handoff, status, the board and the archive | c4f41e1f | none: no row for a release's merged PR | no campaign | scenario only | test_board_prs_release.py::test_a_release_pr_merged_in_the_record_is_not_a_merge_the_record_lacks; test_batch_end.py |
