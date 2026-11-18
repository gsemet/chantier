# Claims of v0.12.0

Since v0.11.0, at 1007ff9 (origin/main). Runs: none.

No eval campaign ran for v0.12.0 (the user's word, 2026-11-18). A claim that a named check of `just scenario` proves is `scenario only`; every other claim is `not exercised`. No claim is `exercised`.

| Claim | Commit | Rail | Can come up in | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| Name stale image links and check carried proofs by position | 1007ff94 | C8 | full, real-foreman, real-direct, claude-planted | scenario only | run_scenario.py, the ship steps |
| Give timing-bound checks a margin on a loaded machine and retry the tool download once | 114738d7 | none: CI-only margin | no campaign | scenario only | run_scenario.py, the timing-bound steps |
| Hand off to a fresh Driver for the closing step after VERIFIED | f3d3f56e | none: no row for the closing hand-off | no campaign | scenario only | run_scenario.py, the closing Driver step |
| Keep a working CR the stack driver has not placed out of the stack's ask | e9f3a795 | none: no row for the stack driver's ask | no campaign | scenario only | run_scenario.py, the stack steps |
| Refuse a main-based PR out of draft that carries another change's commits | 937430f8 | C8 | full, real-foreman, real-direct, claude-planted | not exercised |  |
| Fit the Gantt in its panel at desktop width so the now line stays visible | ef9f9779 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Put the Batch page's central view under graph, Gantt and time-card tabs | 28250cfc | none: the board's page, no run draws it | no campaign | not exercised |  |
| Keep Kanban cards at full height and the Costs receipt's header box | 580f1003 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Write the board's design rules in DESIGN.md and draw every card, column and chip once | c399cf53 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Keep the address's filter and sort on first load and say MR on the remaining GitLab words | c20818f2 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Filter the PRs page by batch and state, sort it, and say MR on GitLab | 1c0ad24f | none: the board's page, no run draws it | no campaign | not exercised |  |
| The CR board pane shows the project its session steers on a planning surface | 63f857ad | none: the board's page, no run draws it | no campaign | not exercised |  |
| Open a PR, an MR, an issue or a link on its site | 25ae09ef | none: the board's page, no run draws it | no campaign | not exercised |  |
| Show where a batch's money went, by model and by role, on the Costs page | 7dcf5a5a | none: the board's page, no run draws it | no campaign | scenario only | run_scenario.py, the Costs steps |
| Stamp the Costs receipt of a batch that is not closed with a red NOT FINISHED | c0c5fa27 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Render the drawer, priority chips and CR titles correctly | c9e645c1 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Name a host and default matrix in a specification and probe it before a CR's first push | 6f1e4f76 | none: no row for a specification's host matrix | no campaign | not exercised |  |
| Print a trigger line when a stack batch's first stack is due | f36277c6 | none: no row for the stack trigger line | no campaign | scenario only | run_scenario.py, the status steps |
| See a stacked PR that landed with its base and tell status to record it | 3b5d13a0 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Tell a compacted session to call its role's skill again with reload | a65a8d3d | none: a compaction no run forces | no campaign | not exercised |  |
| Base a stack CR on the nearest earlier CR with a PR and set the final order once at the batch's end | 70017850 | none: no row for the stack's base | no campaign | scenario only | run_scenario.py, the stack steps |
| Carry a gate pass and a verdict over a rebase by exact patch-ids and record it at ship | a0918624 | C7 | full, real-foreman, real-direct, claude-planted | scenario only | run_scenario.py, the carry steps |
| Print a role's contract when its shipped-default escalation starts as a generic agent | c785e156 | J1 | full, real-foreman, real-direct, claude-planted | not exercised |  |
| Print a role's contract also when its escalation starts as a generic agent | eeab974b | J1 | full, real-foreman, real-direct, claude-planted | not exercised |  |
| Configure the escalation model per host and role, and escalate on every blocked rounds | e3ba4b5c | J19 | full, claude-planted | not exercised |  |
| Print a bare writes line for workers and a scratch folder for Verifiers | 4d3880d8 | J12 | full, real-foreman, real-direct, claude-planted | scenario only | run_scenario.py, the writes line steps |
| Keep the chosen batch of a link at first load and show no duration for a record without dates | 907a48db | none: the board's page, no run draws it | no campaign | not exercised |  |
| Skip the board's 'on this machine:' line before the local-network warning | a7e601c5 | none: the scenario's own step | no campaign | scenario only | run_scenario.py, the board step |
| Batch navigator on the Costs and Batch pages, receipt copied as an image | 1ea3de53 | none: the board's page, no run draws it | no campaign | scenario only | run_scenario.py, the board steps |
| Kanban scrollbar in view, teal priority colours, pastel tints, lighter sidebar and project marks off the state hues | 77d7c10b | none: the board's page, no run draws it | no campaign | not exercised |  |
| Open the overview from the picker's surface item on any page, and make it the menu header | 9bffd7b5 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Show each role's description on the Configuration page | a111e182 | none: the board's page, no run draws it | no campaign | not exercised |  |
| One board per planning surface, other batches listed in preflight and status, per-project staging rule | 33a23059 | none: no row for the board per surface | no campaign | scenario only | run_scenario.py, the board and preflight steps |
| Show the roles-not-recorded line once on the cost receipt of an older record | 5fd088dd | none: the board's page, no run draws it | no campaign | not exercised |  |
| Show the batch's cost on the Costs page as a receipt and record its figures at close | 5fe1d842 | none: the board's page, no run draws it | no campaign | scenario only | run_scenario.py, the close and cost steps |
| Timing and retry settings (steering wake, cache TTL, CI re-runs) in the configuration, per host and model family | de1e69dc | none: no row for the timing settings | no campaign | scenario only | run_scenario.py, the configuration steps |
| A lighter, more elegant web board with Inter, a sticky breadcrumb, state badges and a single PR column | 49414343 | none: the board's page, no run draws it | no campaign | not exercised |  |
| Restart a Driver stopped from outside on the batch's go and flag it in status | c6ab3892 | none: no row for a Driver stopped from outside | no campaign | scenario only | run_scenario.py, the status steps |
| Pause the dry run's batch only when the last merge did not already pause it | 1679df0d | none: the eval kit, no run uses it | no campaign | not exercised |  |
| Pause the batch and clean its merged worktrees when its last CR ends | 7c68507d | J14 | full, claude-planted | scenario only | run_scenario.py, the last-CR end steps |
| Judge only the agents the batch holds, list the session's other subagents apart | d783eaaf | C14 | full, claude-planted | scenario only | run_scenario.py, the close steps |
| Take, take stack and order qa print the Driver's whole prompt skeleton | ad235536 | J1 | full, real-foreman, real-direct, claude-planted | scenario only | run_scenario.py, the take steps |
| Show a CR's hand-back state apart from its PR's draft flag in the stack rows | 8e3ab4bb | none: no row for the stack rows | no campaign | scenario only | run_scenario.py, the stack steps |
| Take the forge's empty unstack reply as a success and say what to run after a failed rebuild | 510965f0 | none: GitLab and the forge stack, no run | no campaign | scenario only | run_scenario.py with fake_gh.py, the forge-stack steps |
| Start Claude campaigns without a Foreman away from the desk | 53b18558 | none: the eval kit, no run uses it | no campaign | not exercised |  |
