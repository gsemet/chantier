# Rules to reread after a compaction

The Chief of Staff and the Foreman read this after a reload or a compaction. The full rules stay where they are.

- **Reports:** before a report, read `status-layout.md` whole and run `status --refresh`. Copy the header from `status`'s first line and its `batch:` line, and each icon from `label`, never judged.
- **The ready words:** say "ready to merge" only for 🟢, "PR in draft" with "do not merge" and what it waits for, "ready locally" for a CR with no PR. "Ready" alone is never used, and the icon is the present state. For each CR you name to the user, copy its `handed back:` line from `status` with the prefix dropped: its icon, its full link, each gap, its `owed before the merge` clauses (the user may merge anyway; record it as any merge) and its long gate clause. Add the local run the Foreman's ask carries (`local gate <cr> at <sha7>: …`); when the ask and the line differ, the ask wins (`chief-of-staff-merge.md`, "The words to the user").
- **The shape:** read it on the `batch:` line. A parallel or series batch runs a project's local-gate rule once per covered PR, a stack once on its top (the project's rules and `driver.md`'s long-gate rule decide who owes it). In a stack, read the manifest's `batch:stack` action and the shape line's `alone asks`.
- **Who merges:** the user only; never merge for the user. Under a release grant, the steering session merges the release PR or its fix PRs, as the `batch:` line says (`under the grant`). A merge the user makes is recorded with `order merged`.
