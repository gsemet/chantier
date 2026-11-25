# The local gate at the top and the hand-back

- The local gate at the mergeable top: when the rules ask the stack's top a local run and the stack has drafts or CRs to come, the top of the mergeable part has passed that gate at its pushed head (`$CHANTIER gate <cr> <name>…` in its worktree, as any long gate; a head with a pass or a `carried:` is not run again; a docs-only top included). A PR that would become the new top turns out of draft only once its gate passed; a failure leaves it a draft, the previous top stands, and `[stack→foreman] anomaly <cr> local gate failed at <head7>: <the log's path>` goes before the hand-back. You change nothing for it.
- Hand-back: `[stack→foreman] hand-back ready to merge <stack link> <cr>=<link>…[ local gate <cr> at <head7>: passed|failed|not run][ <cr> to come: <cr below> not shipped at <tip7>]…`, the gate tail on every hand-back that leaves a partial stack.
- Lease: `lease: stack <n>` on `stack`, `stack --out-of-draft|--draft`, `forge-stack create|rebuild|unstack`. Before the local gate, `lease stack hold --lease <n> --minutes 90`, again at each wake while it runs.
- Making the stack itself: `help stack-make`.
