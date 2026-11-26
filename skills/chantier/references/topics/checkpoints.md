# Commits and checkpoints

A PR merges by rebase with every commit of its branch: each commit you make, a round's or a checkpoint (work set aside, a commit before a gate or after a `FIX-REQUIRED` round), becomes a commit of the default branch.
- Its message follows the project's commit style (its rules; with none, a Conventional Commit subject, as for the PR title) and says what the commit holds. Never a `wip` type, "pending", "checkpoint", a round or a review state, a CR number, a batch or a role. A commit a procedure names (a release's `release: vX.Y.Z`) keeps its message.
- Before the branch's first push, a checkpoint that is your head may be folded into the next round's commit: stage that round's files by name, `git commit --amend -m "<a message for both>"`, then `note <cr> "r<n> folded into <sha>"`.
- Once the branch is pushed, or when the checkpoint is not your head, it stays as it is, with its real message: never a rewrite for a message alone.
