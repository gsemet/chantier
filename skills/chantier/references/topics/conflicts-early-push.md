# The early push

When a rebase of a CR whose PR exists needs a long gate (a `rebase:` note, a restack, a taken-back CR, a resolved conflict):
- Turn the PR to draft if it is not one (`gh pr ready --undo`, `glab mr update --draft`).
- Push at once with `--force-with-lease` (`chantier push`), then `ship <cr> <link>` (`--conflict` when a conflict was resolved). `off: no long gate passed at <sha>` is expected.
- Start the long gate and the CI watch side by side, each in its own background shell, by the outcomes of `help ci-beside-gate`: a red CR job stops the gate, a failed gate stops the watch.
- The PR leaves draft (`gh pr ready`, `glab mr update --ready`, then `ship`) only once the gate has passed and CI is green at that same head.
- A PR that does not exist yet waits for its gate before its first push, unless the project chose `ci: beside_gate: true`.
- With a long gate of the CR running, stop it (`gate <cr> --stop`) before the rebase.
