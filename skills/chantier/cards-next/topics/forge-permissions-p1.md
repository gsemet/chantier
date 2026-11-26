# Forge permissions (P9), GitHub (part 1 of 2)

At your first turn of a session and again at step 1 of a batch, check that the batch's forge operations will go through: read-only, each command alone; on Windows PowerShell 5.1 print `--json` and read the JSON, with no `--jq` or `--template` expression that holds spaces. A CLI not logged in still fails P9 for a batch. Everything below only warns, and the batch starts whatever it says.
1. `gh auth status` and its `Token scopes:` line: `repo` (a fine-grained token prints none: say "unknown: a fine-grained token, see its permissions") and `workflow`. A missing `workflow` is said only as "needed by a CR that touches `.github/workflows/`"; at step 1 name the plan's CRs that do.
2. `gh repo view --json viewerPermission,defaultBranchRef`: `WRITE`, `MAINTAIN` and `ADMIN` can push, edit PRs and publish a release; `READ` and `TRIAGE` cannot: say so.
3. The rules over `chantier/` branches: `gh api repos/<owner>/<repo>/rules/branches/<a chantier/ branch name>` (the name need not exist; write its `/` raw; the endpoint answers it like `%2F`). A `non_fast_forward` rule refuses the force push, `update` the push, `creation` a new branch: name each with its ruleset. The legacy branch protection is read only for an `ADMIN` account, else say "not readable with your rights".

A stack, a merge by the steering session, GitLab and what the user hears: part 2.
