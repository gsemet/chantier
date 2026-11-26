# A Driver's refused rebase

The same ladder as the force push (you, then the Chief of Staff, then the user's one question if the host refuses both; in direct mode Driver, Chief of Staff, the user). A named exception to "no `git rebase`": only this command, only in a Driver's worktree, only on such a line. You resolve nothing.
1. On `[driver <cr>→foreman] rebase <branch> <base>` the check is a hard refusal: the branch is covered (`chantier/*`, not the default branch), the CR is read from its last segment, `$CHANTIER handoff <cr>`'s `worktree: … branch <branch>` line gives exactly it, and `<base>` is the `base` it prints. Else rebase nothing: `take <cr> --note "rebase: rebase refused <branch>: <reason>"`.
2. Claude Code: the P10 `every batch:` line names the rebase rule you will run (`git -C * rebase origin/*`, `git -C * rebase chantier/*`, `git -C * rebase --onto …`; `origin`: the project's remote) in an `(add …)` part or under `denied:`: rebase nothing, `$CHANTIER note <cr> "rebase not tried: rule missing"`, and send the line of step 4 at once. Copilot skips it.
The run and the answer: `help refused-rebase-run`.
