# Claims of v0.15.0

Since v0.14.0, at a5d928a (origin/main). Runs: real-foreman-2026-11-22-run4.md.

One eval run only: real-foreman, run 4, 2026-11-22, in stack mode. `full` and real-direct did not run before this release (the user's word, 2026-11-22: "Run 4 suffit"). A claim is `exercised` only when run 4's Scorecard marks its Rail `seen, right` or `seen, wrong`. A claim that a named check of `just scenario` or `just test` proves is `scenario only`; its evidence names the test or scenario files that the commit changed (not each case). Every other claim is `not exercised`.

| Claim | Commit | Rail | Can come up in | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| A native stack's merges into the branch below are told landed | 392b2811 | none: no row for board | no campaign | scenario only | test_board_forge_read.py, test_board_prs.py, test_forge_hub.py |
| Refuse a missing project clone instead of crashing | b2ea51bf | none: no row for open | no campaign | scenario only | test_cli_units.py, test_open_no_clone.py |
| One base function for an unplaced CR of a stack batch | 0b7868b7 | none: no row for stacks | no campaign | scenario only | test_stack_base.py |
| A placed CR keeps only its recorded start base | db0000e7 | none: no row for stacks | no campaign | scenario only | run_scenario.py, test_stack_base.py |
| A clean rebase in a stack carries whatever branch the record names | 8d67da41 | C7 | full, real-foreman, real-direct, claude-planted | exercised | real-foreman-2026-11-22-run4.md, C7 seen, right (CR-105's gate carried over a clean rebase) |
| Hold a ready CR out of the stack | f9087d67 | none: no row for order | no campaign | scenario only | run_scenario.py, test_stack_hold.py |
| A CR started on a held CR starts on the default branch | c992715b | none: no row for stacks | no campaign | scenario only | test_stack_hold.py |
| An ended start_on owner still falls back below; only a held one goes to the default branch | fe825f70 | none: no row for stacks | no campaign | scenario only | test_stack_hold.py |
| Record and show a CR's plain subject, without the Change Specification lead | c79f01e7 | none: no row for titles | no campaign | scenario only | test_board_prs.py, test_board_prs_batches.py, test_titles.py |
| Just tag fast-forwards the main checkout before it tags | fd970ca9 | none: no row for release | no campaign | scenario only | test_release_tag.py |
| Version.py dispatches the ff-main subcommand | f1d1c911 | none: no row for release | no campaign | scenario only | test_release_tag.py |
| Order drop names where the CR goes (trash, inbox or backlog) | a6a4ac22 | none: no row for orders | no campaign | scenario only | test_batch_end.py, test_factory.py, test_forge_moved.py, test_order_drop_to.py |
| One Driver per CR, a smaller driver card and a closing step that resumes from the record | 299d2c1f | J2 | full, real-foreman, real-direct, claude-planted | exercised | real-foreman-2026-11-22-run4.md, J2 seen, right (a CR Driver per CR) |
| A CR taken out of a batch comes back under its number, with its branch and PR | 1f86ece9 | none: no row for cli | no campaign | scenario only | run_scenario.py, test_came_back.py, test_rail_refusals.py |
| The long gate's queue survives a sharing violation on a ticket or mark | 8bd198b1 | none: no row for gate | no campaign | scenario only | test_gate_queue_order.py |
| Typed events name@N, version 2 lines, published schemas | 3866d764 | none: no row for journal | no campaign | scenario only | run_scenario.py, test_board_config.py, test_board_journal.py, test_board_prs.py |
| Read the typed journal lines and a full-length head | 7afbc5f3 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| The plan's storage behind a minimal store interface | a8f17555 | none: no row for cli | no campaign | scenario only | test_store_command_table.py, test_store_conformance.py |
| Driver leases on what take gave them: --lease, lease renew/hold, take --reclaim | e461ffd2 | none: no row for cli | no campaign | scenario only | run_scenario.py, test_leases.py, test_rail_refusals.py, test_spend_check.py |
| A CR's title stays short, at most 72 characters, checked by validate, summary lint, file and the board | 56681802 | none: no row for cli | no campaign | scenario only | test_board_design.py, test_board_journal.py, test_summary_lint.py, test_titles.py |
| The board's idea text starts with a heading; the no-heading refusal says so | d2f56037 | none: a scenario step | no campaign | scenario only | run_scenario.py, test_titles.py |
| A several-line request with no heading is refused with the long-title message, as specified | dda8ac97 | none: no row for cli | no campaign | scenario only | test_titles.py |
| Forge connectors as plugins, and a hub that polls only what is awaited | c51aea6a | none: no row for cli | no campaign | scenario only | test_board.py, test_board_forge_read.py, test_board_prs.py, test_board_prs_unclaimed.py |
| An outside poller writes issue events into the journal | 75a73d59 | none: no row for cli | no campaign | scenario only | run_scenario.py, test_forge_hub.py, test_outside_poller.py, test_watch_events.py |
| Typed waits, a CR records what it waits for | 9b55b0a4 | none: no row for cli | no campaign | scenario only | run_scenario.py, test_board_waits.py, test_forge_hub_waits.py, test_store_command_table.py |
| Typed_waits case in the gitlab unit, with the fake glab's graphql answer | 1acb0d66 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| Split the Driver's record registration to keep functions small after the rebase | 8febc005 | none: no row for cli | no campaign | not exercised |  |
| Keep the merged hub journal docstring short and Interest's meta a keyword after the rebase | 18a6c0c2 | none: no row for cli | no campaign | not exercised |  |
| The surface server commits, rebases and pushes the plan | f7c18f1a | none: no row for writer | no campaign | scenario only | run_scenario.py, test_autosync.py, test_board.py, test_board_config.py |
| The test's pre-commit hook is executable, so git runs it on POSIX | bd5befc7 | none: no row for writer | no campaign | scenario only | test_writer_cycle.py |
| Archive a PR merged without chantier; validate checks an outside archive's name | 9bd055ec | none: no row for archives | no campaign | scenario only | test_validate.py |
| Access explains why a session may or may not write, claim or push | daec1986 | none: no row for cli | no campaign | scenario only | test_access.py |
| The server's API over a WebSocket, the web board one client among others | ef2361fb | none: no row for board | no campaign | scenario only | run_scenario.py, test_board.py, test_board_config.py, test_board_journal.py |
| The web client moves to clients/web; board --ui <folder>|none | d7b5a019 | none: no row for board | no campaign | scenario only | run_scenario.py, test_board.py, test_board_config.py, test_board_design.py |
| Downloaded CI artifacts stay out of the published plan; path-too-long blocked reason | e9f086af | none: no row for writer | no campaign | scenario only | test_startup_manifest.py, test_store_conformance.py, test_writer_edges.py, test_writer_lines.py |
| Take's base and the ready word follow the forge | 96d5e0b7 | none: no row for cli | no campaign | scenario only | run_scenario.py, test_stack_base.py, test_stack_hold.py |
| Chantier live, a read-only terminal client of the board's API | bbb236fe | none: no row for cli | no campaign | scenario only | run_scenario.py, test_board.py, test_board_ui.py, test_leases.py |
| The plan's store reads the planning folder through one read interface | c710478b | none: no row for store | no campaign | scenario only | test_batch_end.py, test_board_archived.py, test_board_config.py, test_board_description.py |
| Callers of journal.read pass the store after the restack | ddc5a525 | none: no row for store | no campaign | scenario only | test_stack_base.py |
| Journal.py import order after the restack | 18f2ac2b | none: no row for store | no campaign | not exercised |  |
| Listen on this machine by default, open to the network on ask, cookie lasts 30 days | d60b3538 | none: no row for board | no campaign | scenario only | run_scenario.py, test_board_exposure.py, test_playbook_layers.py |
| Replace the factory mode with a choice of destination at the grill | 3b3eba06 | none: no row for it | no campaign | scenario only | run_scenario.py, test_batch_end.py, test_came_back.py, test_factory.py |
| The Foreman parks a CR stuck on an outside wait | 99fa847f | none: no row for park | no campaign | scenario only | run_scenario.py, test_came_back.py, test_park.py, test_park_back.py |
| Hold a live CR in every batch mode | e7feda55 | none: no row for order | no campaign | scenario only | run_scenario.py, test_came_back.py, test_hold_live.py, test_hold_live_modes.py |
| Split the backlog's last column into running batch and next batch | adca88a1 | none: no row for board | no campaign | scenario only | run_scenario.py, test_board_running_lane.py, test_event_audience.py, test_server_api_calls.py |
| Allow rules name real paths and broad ones are named | 33d10454 | none: preflight's P10 has no row | no campaign | scenario only | run 4 saw P10's warning (its finding 13) but no rail marks it; run_scenario.py, test_allow_rules.py, test_cli_runs.py |
| Drop a CR to ready, never to the inbox | ab2e44cf | none: no row for order | no campaign | scenario only | run_scenario.py, test_came_back.py, test_order_drop_to.py |
| The inbox refusal of order drop exits usage | fc537bfd | none: a scenario step | no campaign | scenario only | run_scenario.py |
| Batch page Kanban of the batch's three folders | e4171908 | none: no row for board | no campaign | scenario only | test_board_design.py |
| A batch CR's card shows its batch folder, not its old priority chip | 16949f41 | none: no row for board | no campaign | scenario only | test_board_design.py, test_board_times.py, test_board_waits.py |
| Dev mode only for chantier itself, other projects in plugin mode | 906e5fd1 | none: no row for launch | no campaign | scenario only | run_scenario.py, test_allow_rules.py, test_launch_modes.py, test_plugin_files.py |
| The last readers read the planning folder through the store | eb69264a | none: no row for store | no campaign | scenario only | test_gate_queue_order.py, test_leases.py, test_outside_poller.py, test_store_reads.py |
| Recognise stdlib frames by real path in the store run-time proof | e5dc6952 | none: no row for test | no campaign | scenario only | test_store_runtime.py |
| Wait out a held CR folder on Windows, then refuse with the cause | 27269e99 | none: no row for store | no campaign | scenario only | test_triage_moves.py |
| A refused force push climbs Foreman, Chief of Staff, then the user | 0e36d1f8 | J11 | full, real-foreman, real-direct | scenario only | run 4 did not see J11 (no refused push); test_came_back.py, test_cli_runs.py |
| Dashboard page, productivity and spending by closed batch | e3877937 | none: no row for board | no campaign | scenario only | test_board_dashboard.py, test_board_design.py, test_server_api_calls.py |
| The welcome lists 21 ops since dashboard.get | 42063735 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| The server watches the planning files and reads the forge only while observed | 22bc9e51 | none: no row for board | no campaign | scenario only | test_access.py, test_board_exposure.py, test_board_idle.py, test_board_prs.py |
| The watcher subscribes to the surface server and starts the board | 4f0ff6d8 | none: no row for watch | no campaign | scenario only | test_event_audience.py, test_forge_hub.py, test_live_link.py, test_surface_server.py |
| A transient read error no longer erases the server's state entries | ef4eff6d | none: no row for hub | no campaign | scenario only | run_scenario.py, test_state_lost_update.py |
| Keep the events frames seen while waiting for a move result | 54736c33 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| The server scenario's cli_form follows the plugin-mode form | cb914330 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| A blocked uv sync names chantier's holders, waits, never kills | 56f753e6 | none: no row for sync | no campaign | scenario only | test_allow_rules.py, test_launch_modes.py, test_plugin_files.py, test_startup_manifest.py |
| An Inbox page of what needs the user | e15fccb3 | none: no row for board | no campaign | scenario only | test_board_inbox_design.py, test_board_needs.py |
| Tell a dev session when the surface server runs a foreign build | 687a4723 | none: no row for board | no campaign | scenario only | test_board_running.py, test_forge_hub.py, test_launch_modes.py, test_watcher_autostart.py |
| The Batch page's mode and legend move into the title row | 35ab0d19 | none: no row for board | no campaign | scenario only | test_board_design.py |
| Fold each Triage priority row and explain the writes count | 82cebbc4 | none: no row for board | no campaign | scenario only | test_board_design.py |
| One arrowhead per waiting CR, lit arrows on top, a tooltip on the mode switch | 49245a7b | none: no row for board | no campaign | scenario only | test_board_graph_arrows.py |
| Check an ordered stack as a git chain at ship and stack --out-of-draft | aa0befe3 | C8 | full, real-foreman, real-direct, claude-planted | scenario only | run 4 marked C8 `seen, right in part` (its finding 6), not `seen, right`; run_scenario.py, test_hold_live_shared.py, test_stack_chain.py, test_stack_chain_cards.py |
| Run only named long gates and make lease hold run nothing | 2a19b7de | none: no row for gate | no campaign | scenario only | run_scenario.py, test_access.py, test_carry_ship.py, test_cli_runs.py |
| Name the gate under a project flag and ignore the harness's own chantier.yaml | 3b76a63e | none: a scenario step | no campaign | scenario only | run_scenario.py |
| Keep the lease-hold file pattern constant after the restack | 9f847fc5 | none: no row for board | no campaign | not exercised |  |
| History page of what was done per day, week or month | dda590d9 | none: no row for board | no campaign | scenario only | run_scenario.py, test_board_history.py, test_board_history_client.py, test_server_api_calls.py |
| The welcome check counts the 21 ops and 7 topics | 8a295840 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| Keys to scroll and filter, and up to four boards in one screen | dce2c644 | none: no row for live | no campaign | scenario only | test_board.py, test_live_link.py, test_live_model.py |
| A stack batch keeps its shape after compactions | a70d0557 | none: no row for stack | no campaign | scenario only | run_scenario.py, test_came_back.py, test_plugin_files.py, test_stack_chain_cards.py |
| The Batch page's mode and legend move into the title row | 24ae4045 | none: no row for board | no campaign | scenario only | test_board_design.py |
| A Help page of chantier's concepts and roles | dc50ba39 | none: no row for board | no campaign | scenario only | test_board_design.py, test_code_targets.py |
| The phone's bottom bar scrolls sideways when its items no longer fit | 9e2a29f9 | none: no row for board | no campaign | not exercised |  |
| Batch graph with transitive reduction, merged CRs folded, fewer crossings | 63e23360 | none: no row for board | no campaign | scenario only | test_board_graph_arrows.py |
| The board's Griller roles, defaults and rules (round 1) | 86fe6966 | none: no row for griller | no campaign | scenario only | test_playbook_layers.py, test_plugin_files.py, test_startup_manifest.py |
| The board's Griller engine, API ops, write guard and docs (rounds 2-3) | 113bf187 | none: no row for griller | no campaign | scenario only | test_board_griller.py, test_board_griller_api.py, test_server_api_calls.py, test_store_reads.py |
| Fit the startup size and code-size gates after the rebase | 72886c96 | none: no row for griller | no campaign | scenario only | test_plugin_files.py |
| The web board's Grill button and discussion panel (round 4) | ce706c2d | none: no row for griller | no campaign | scenario only | test_board_griller.py, test_board_griller_client.py, test_plugin_files.py |
| Start a stack CR on another CR's branch only once it is ready | 92c7a795 | none: no row for stack | no campaign | scenario only | run_scenario.py, test_stack_base.py |
| Rename the surface server's command to serve; add webui | f7171e1f | none: no row for cli | no campaign | scenario only | run_scenario.py, test_access.py, test_board.py, test_board_exposure.py |
| The link's cookie carries the server's per-server cookie name | 7fab8717 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| Init the planning folder of serve_and_webui's surfaces | 0ae11477 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| Serve_and_webui starts its servers without a seat | d61a0a60 | none: a scenario step | no campaign | scenario only | run_scenario.py |
| A public read-only key beside the private key | dd30ecd7 | none: no row for board | no campaign | scenario only | run_scenario.py, test_board_exposure.py, test_board_griller_client.py, test_board_idle.py |
| A paste field for a lost key and SameSite=Lax cookies | bb8765a4 | none: no row for board | no campaign | scenario only | run_scenario.py, test_board_exposure.py, test_board_key_page.py |
| Run CLI commands remotely through the surface server | 28bb7f91 | none: no row for cli | no campaign | scenario only | run_scenario.py, test_remote_cli.py, test_server_api_calls.py |
| The server's welcome counts the new cli.run op | 5691a05d | none: a scenario step | no campaign | scenario only | run_scenario.py |
| Make the live --only refusal and the folder-lock test deterministic | a5d928a9 | none: no row for test | no campaign | scenario only | test_live_model.py, test_triage_moves.py |
