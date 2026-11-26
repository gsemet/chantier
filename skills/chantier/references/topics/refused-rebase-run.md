# A Driver's refused rebase: run it

3. Run one command: `git -C <worktree> rebase <base>`, in a clean worktree, after `git -C <worktree> fetch <remote>`. Clean: note `rebased <branch> onto <base> at <sha7>` and take the CR back with `rebase: rebased <branch> onto <base> at <sha7>`. A conflict: leave the rebase stopped (no `--abort`, no resolution) and take it back with `rebase: rebase conflict <branch> onto <base>`. Never `--exec` or `-x`.
4. The host refuses you: `$CHANTIER note <cr> "refused: <the exact command> -> <the host's exact text>"`, then `[foreman→chief-of-staff] rebase <branch> <base>`, not through `asks`; wait for `rebased …`, `rebase conflict …` or `rebase refused <branch>: <text>`; retry nothing, change no permission setting.
5. The way back is the push's (`help refused-answer`), with the note `rebase: <the answer>`.
