# A Driver started again

A `take` note `resume:`, `rebase:`, `context:` or another `Note:` says why the unit is with you. Run `$CHANTIER handoff <cr>` and `log <cr>` first, then read only what the steps still to do need.
- `resume: closing`: read `pr-body.md`, `work/verify.md` and the evidence files it names, by name and caption, not opened (a text file a body line needs excepted); the PR template only before the first body edit, and only the sections that edit needs. Do not open the specification, `investigation.md`, the `r<n>.md` notes or the diff. Start at the first closing step with no `closing:` note in the log (`$CHANTIER help closing`). A step outside the closing (a red check, a move, a review item on the code, a `rebase:` note) brings back the usual reads.
- A Driver resumed before the first push starts at the push and the PR, not at the closing.
- `stop hold: <O-n>` (the user held your CR): commit nothing new, leave the worktree as it is, answer the steering session `stopped: held; worktree clean|dirty: <files>`; your next leased command is `claim lost`.
- `rebase:`, `restack`, `folded:`, `unhold:` or another re-take note: `$CHANTIER help retake`.
