# Where a dropped CR goes

- The user's word that takes a CR out of a batch ("drop", "take it out", "postpone", "remove from the batch") names where it goes. When it does not, ask once, in the user's language, before the order: the trash (cancelled), the next batch (`ready`, `3-ready`) or the backlog P1..P4 (postponed or handed off; the usual case for delegated work). A word that already says it needs no question ("cancel it" is the trash; "postpone it, P2" is `P2`).
- Never choose for the user: `order drop` is refused with no `--note`. The inbox is not one of them, for any CR: a CR already planned has no reason to go back to the inbox (`--note inbox` is refused); a later move of its folder, the inbox included, is `triage` or the board on the user's word.
- A word that only keeps a CR out of the order for now (a ready CR of a stack, or a live CR in any mode) is `order hold`, not a drop.
- Whatever the destination, the CR keeps its work (worktree, branch, PR); only the trash closes its PR; the backlog and the next batch keep it as a draft. A CR moved to the backlog or `3-ready` keeps its number (`formerly.json` in its folder).
