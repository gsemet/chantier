# Claims of v0.11.0

Since v0.10.0, at d15df0b (the top of batch-22's stack; origin/main is at 7ae5958, and the stack's five changes are not merged yet). Runs: none yet.

No campaign has run for v0.11.0. The two campaigns chosen for it, `real-direct` in stack mode and `real-foreman` in parallel mode, could not start on the night the version PR was prepared (the app refused to start the operator session under Remote Control); they run at the desk after the stack is merged and before the version PR is, and this file is completed from their reports. `full` and `copilot` are not run for this release (the user's word of 2026-11-17). Every result below is therefore `not exercised`, campaign pending. The commit `9eaef4a` (the short startup core, a `wip:` commit, so no row) changes how every role starts: the campaigns are what bring it to the test.

| Claim | Commit | Rail | Can come up in | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| Run each Copilot role on its chosen model and add a model check for the Copilot evaluation | faa4719 | none: Copilot, no scorecard row | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Build the Copilot model catalog from GitHub's own tables | 944f93c | none: Copilot, no scorecard row | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Read chantier's configuration in four layers with shipped model defaults | 2faa446 | none: no scorecard row for the configuration layers | real-foreman (parallel, Foreman), real-direct (stack, direct) | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Start a role on its configured model on each host, with a generic agent where the host cannot | a92113f | J1 | real-foreman (parallel, Foreman), real-direct (stack, direct) | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| A Configuration page on the board edits each role's agent and model per host in the planning surface's project file | 4fc8ba8 | none: the board's page, no run draws it | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| A live, read-only PRs page reads the batch's PRs from the forge | edf4642 | none: the board's page, no run draws it | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Signal a merge the PRs page sees in a local file that status prints | 849ac8c | J26 | real-foreman (parallel, Foreman), real-direct (stack, direct) | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Cap Triage cards, lay the backlog out as a grid and close the panel on a view change | 066c34d | none: the board's page, no run draws it | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Give every Triage card the same width at every window size | 942e14d | none: the board's page, no run draws it | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Show the planning surface in the selector and each project's folder and repository | cc56e3c | none: the board's page, no run draws it | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Let the picker button's project count wrap so its number stays readable | 51a3c8e | none: the board's page, no run draws it | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
| Write the project file with LF from the Configuration page, also when the file had CRLF | d15df0b | none: the board's write path, no run uses it | no campaign | not exercised | campaign pending (real-direct stack, real-foreman parallel) |
