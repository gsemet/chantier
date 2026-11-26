# The answer to a refused push or rebase

A fresh Driver reads the answer in its `take` note and goes on from the `next after push` (or `next after rebase`) note.
- `push: pushed <branch>`: `ship`, then the steps left.
- `push failed`: look at why (`git fetch`, what the remote gained); never the same push again.
- `push refused <branch>: no long gate passed at <sha>`: run the long gate, then hand back `waits:` again as `help refused-push` says. With the `ci: beside the long gate` line, or for a branch whose PR is recorded, the steering session does not send this push: pass one you get to the steering session as printed.
- `rebased <branch> onto <base> at <sha7>`: push and go on.
- `rebase conflict <branch> onto <base>`: the rebase stopped at the conflict in the worktree; start a `conflict-resolver` on it.
- Any other refusal (a branch not this batch's, a push judged not legitimate, the host refusing at every step, a forge rejecting a protected branch, `rebase refused <branch>: <text>`): `handback <cr> blocked refused <exact text>` at once; it goes to the user.
