# Inspector: the audit of a CR's round

The pr-body, a host and default matrix, and a move's carry.

- `pr-body.md`: on a CR's round, read `<work folder>/pr-body.md` with the diff and audit it against the project's PR template and rules, else against [pr-template](../pr-template.md) (its audit list). When the CR was grilled, also read the CR's `02-answers.md` (in the CR's folder, the parent of the work folder), for the Human decisions item. A missing `pr-body.md` or a failed audit item is `blocking`, written `pr-body.md: <section>: …`.
- Matrix: when the specification or your prompt names a host and default matrix ([concepts](../concepts.md), "Words"), each cell needs a test or a check in the diff that runs its real flow. A cell with none, or one tested only on a record or configuration shape built by hand, is `blocking`.
- Carry: given a move (`<old head>..<new head>` and its kind), review only what the move changed in the CR's own patch: `git range-diff <old base>..<old head> <new base>..<new head>` for a rebase or a restack, the diff for a resolved conflict. Say in `minor` what you carried unchanged.
