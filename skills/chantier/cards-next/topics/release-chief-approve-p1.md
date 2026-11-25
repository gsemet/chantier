# The post-merge word, asked with the merge go (part 1 of 2)

When the release PR is offered (the `ready-to-merge <release-cr>` ask, or the complete `stack-ready-to-merge` whose top is the release PR), ask in that same message the user's word for each irreversible step the procedure runs after the merge, each on its own (chantier: CONTRIBUTING.md "Release" step 4, `just tag`, and step 5, `gh release create vX.Y.Z --verify-tag ...`). They may answer yes to all, some or none. Never the merge itself, and never the announcement: both stay the user's.
- A yes: before `order merged`, one `$CHANTIER order approve <release-cr> --note "<step>: user, <YYYY-MM-DD>: '<the user's words>'"` per step; answer and merge in one message: approvals first. Foreman mode: all lines in one message.
- No word: record nothing; the Driver started at the merge hands back `blocked approval: <step>`, the ask follows, the answer is `order approve`.
- A release redone before its merge: the yes already recorded holds and is not recorded again; the next ready line names the steps already approved (from `approvals unused:` in `handoff <release-cr>`) and asks only for the rest.
