# Forge permissions (P9), GitHub

At the first turn and at step 1 of a batch, read-only, each command alone; on Windows PowerShell 5.1 print `--json` and read it, no `--jq` with spaces. Everything only warns.
1. `gh auth status` and its `Token scopes:` (`repo`; a fine-grained token prints none: say "unknown: a fine-grained token, see its permissions"; `workflow` only for a CR touching `.github/workflows/`, named at step 1).
2. `gh repo view --json viewerPermission,defaultBranchRef`: `WRITE`, `MAINTAIN`, `ADMIN` can push, edit PRs and publish; `READ`, `TRIAGE` cannot.
3. `gh api repos/<owner>/<repo>/rules/branches/<a chantier/ branch name>` (the name need not exist, `/` raw): `non_fast_forward` refuses the force push, `update` the push, `creation` a new branch: name each with its ruleset. Legacy protection is read only for an `ADMIN` account.
4. A stack: `gh api repos/<owner>/<repo>/stacks -X GET -F per_page=1`; a 404 or 403 means no native stack: `forge-stack create` or the extension will fail and the stack stays a chain.
5. For a merge by the steering session or a stack: the default branch's rules and `gh repo view --json mergeCommitAllowed,rebaseMergeAllowed,squashMergeAllowed`. Warn on required approving reviews (the grant's merge stops), required status checks (said), a merge queue, and the project's merge method not allowed.
GitLab: `help forge-permissions-gitlab`. What the user hears: `help forge-permissions-say`.
