# Claims of v0.13.0

Since v0.12.0, at 4bf3f58 (origin/main). Runs: none.

No eval campaign ran for v0.13.0 (the user's word, 2026-11-18). A claim that a named check of `just scenario` or `just test` proves is `scenario only`; every other claim is `not exercised`. No claim is `exercised`.

| Claim | Commit | Rail | Can come up in | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| A CR's archive stays out of the PR unless the project says yes | 4bf3f582 | C8 | full, real-foreman, real-direct, claude-planted | scenario only | test_external_archive.py::test_an_external_project_keeps_the_archive_out_of_its_pr_unless_it_says_yes; run_scenario.py, the surface-board unit's `take` step |
| A session whose chantier CLI cannot run stops at once | 179afb7d | none: no row for a CLI that cannot run | no campaign | not exercised |  |
| Print a folder path that summary set can read in the lint hint | ef3d423d | none: no row for the summary lint | no campaign | scenario only | test_summary_lint.py::test_the_summary_lint_hint_is_a_path_summary_set_reads |
| Hide a document's front matter in the panel | 7be9c543 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Ignore work/gates/ at any depth of the planning folder | 4a49d5c7 | none: no row for the planning folder's ignore list | no campaign | scenario only | test_driver_prompt.py::test_an_old_work_gates_line_is_completed_with_the_any_depth_one |
| Print the forge hub and watch lines after the last closed batch | 5717626d | none: no row for the forge hub | no campaign | scenario only | run_scenario.py, the surface-board unit's forge hub steps; test_forge_hub.py::test_status_and_the_start_line_name_the_journal_the_hub_and_its_version |
| One forge hub per surface and machine, and watchers that wake each session | a7f32370 | none: no row for the forge hub; the session's wake needs a real host | no campaign | scenario only | run_scenario.py, the surface-board unit's forge hub steps (the hub and the watchers, not a session's wake); test_forge_hub.py |
| Show the batch's shape next to its slots in the CR board pane | f02fbbf1 | none: the pane, no run draws it | no campaign | not exercised |  |
| Show the same steering figure in the board receipt and the cost text | 3c4bf53f | none: the board's page, no run draws it | no campaign | scenario only | test_cost_switch.py::test_the_receipt_shows_the_steering_outside_the_budget_the_text_prints_after_a_switch |
| Start a CR Driver in its worktree and stop background tasks when done | 327b8107 | none: no row for a Driver's start folder or its background tasks | no campaign | not exercised |  |
| Add a project logo and a t3.json that points T3 Code to it | 1d6b0735 | none: a repository file, no run uses it | no campaign | not exercised |  |
| Switch a Foreman batch to direct mode with CRs in flight | bdd27e0f | none: no row for the switch to direct mode | no campaign | scenario only | test_rail_refusals.py::test_the_chief_of_staff_claiming_a_foreman_batch_makes_it_direct |
