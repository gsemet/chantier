# The stack driver: its hand-back asks

On its `hand-back ready to merge <stack link> <cr>=<link>…`, read the stack on the forge, the five checks (`help stack-checks`), then:
- the first stack made: `$CHANTIER asks "stack-ready-to-merge <stack link> partial stack mergeable below <sha7> merge <cr> <link> <cr>=<link> gaps: … local gate <cr> at <sha7>: passed to come: <cr> <cr>…"` (`merge <cr> <link>`: the highest PR of the mergeable part, whose head is `<sha7>`, as `forge-stack show` printed it; the pairs: the mergeable part, each CR's gaps after its link; `to come:` the drafts on top and `forge-stack show`'s `to come:` CRs). Under a rule asking the stack's top a local run, copy the clause from the hand-back and send only with `passed`, for that `<sha7>`; no clause under the rule is a failed check: `take stack --note "local gate at the mergeable top"`.
- the stack complete: `asks "stack-ready-to-merge <stack link> mergeable below <sha7> merge <cr> <link> <cr>=<link>…"`, gaps after each link.
- any other hand-back (a join, a draft turned ready, a restack): no ask.
