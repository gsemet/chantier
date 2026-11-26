# Merging under the grant

A release PR or a fix PR is merged only under the grant: every other CR merged or cancelled, its base the default branch, `$CHANTIER release go <cr> --note "merge <pr>"` saying `go`, and the local run passed when owed (`help local-gate`); a fix with no grant is an ordinary CR handed back. Then the merge by the project's method, `$CHANTIER order merged <cr> --epoch <n>`, then the fast-forward (`help main-checkout`). Direct mode: the Chief of Staff follows the same route. GitLab keeps `glab mr merge`. On GitHub (unproved by an agent), `gh pr merge` is refused for a PR of a native stack:
1. `gh api -X GET repos/<owner>/<repo>/stacks -F per_page=100`: is there an open stack whose `pull_requests` holds the PR among its open ones?
2. None: `gh pr merge <pr> --<the project's method> --match-head-commit <head SHA>` (`gh pr view <pr> --json headRefOid`).
3. One, with an open PR below it: no merge. `[foreman→chief-of-staff] release <cr>: PR <pr> is in a stack above open PRs <numbers>; not merged`.
The asynchronous merge: `help merge-github`. Anything else, or a refused call: a stop with the exact text; no other route, `gh pr merge` included.
