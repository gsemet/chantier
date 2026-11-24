# Foreman: an early conflict check

## An early conflict check (parallel batch)

- **An early conflict check (parallel batch).**
  - **When:** the batch's mode, read from `status`, is `parallel`. A CR's Driver hands it back
    `ready` with a PR (`hand-back ready to merge <link>` or `hand-back PR in draft <link>`), and
    at least one other CR of the batch is `ready` with an unmerged PR on the default branch. Run
    it once per such hand-back, after you send that CR's own ask (`ready-to-merge` /
    `pr-in-draft`), which goes up unchanged. A hand-back after a `take <cr> --note` (a rebase, a
    fix) is a new hand-back and is checked again. It does not run in a `series` or `stack` batch:
    there the PRs are already placed on one another, and a conflict is the stack driver's
    `anomaly <cr> conflict: …`.
  - **Which pairs:** the new CR against each other CR that is `ready`, has a PR whose base is the
    default branch, and is not merged or cancelled. Skip a pair when one CR's base is the other's
    branch (a chain or a dependency: `after`, `depends.json`). Skip a pair already noted (see "On conflicts").
  - **The command,** one per pair, from the main checkout (with a planning surface, `git -C
    <clone>`, the clone `take` names), with each CR's branch as `handoff <cr>` prints it: `git
    merge-tree --write-tree --name-only --no-messages <new cr's branch> <other cr's branch>`.
    Exit 0: no conflict, nothing to do. Exit 1: a conflict; the lines after the first (the tree
    id) are the conflicting paths. Any other exit (a missing ref, a git older than 2.38 that does
    not know `--write-tree`): no ask about a conflict; record `$CHANTIER note <new cr> "early
    conflict check: not run against <other cr>: <git's text, first line>"` and go on. Never fall
    back to another command: no trial merge in a checkout, no `git merge`, no `git rebase`, no
    worktree. A command the host refuses takes the usual route (the `refused <cr> <text>` ask and
    its note, as in [foreman-refused](foreman-refused.md)).
  - **On conflicts:** for each conflicting pair, record `$CHANTIER note <new cr> "early conflict:
    with <other cr>: <paths>"` (up to five paths, then `and <k> more`). This note is the pair's
    source for any later brief, and it marks the pair as noted. Then send **one** ask for this
    hand-back covering every new pair: `$CHANTIER asks "conflict <new cr> with <other cr>[,
    <other cr>…]: <paths>; switch to a stack?"`, each CR named by number and slug together
    (`concepts.md`, "A CR's name"). The ask holds no other proposal. A pair already noted on
    either CR gives neither a note nor an ask again.
  - **What it does not do:** it stops no Driver, sends no `take`, no rebase note and no message
    to a Driver, changes no order, and never switches the mode itself. Each PR stays as its
    hand-back left it: a `ready-to-merge` PR stays mergeable on its own. The switch comes only
    as the Chief of Staff's `order mode --note stack`, which "A mode switch" in [foreman-hold](foreman-hold.md) already
    covers. The stack driver orders the CRs from the record (the CRs handed back `ready` at the
    bottom, in the order they became ready: `concepts.md`, "Batch modes"), so the later CR is
    rebased onto the earlier, once, on the `anomaly <cr> conflict: stacked on <cr>: <files>`
    route and its `take <cr> --note "rebase: stacked on <cr below>: conflict in <files>"`.
  - **Marks:** the check is plain git, the same on both hosts and forges; its run by a Copilot
    Foreman is **unproved**. On GitLab the stack it may lead to is the chain of MRs merged one at
    a time from the bottom, as [foreman-stack](foreman-stack.md) already says: **unproved** on a real GitLab (trial: one
    run on a GitLab project).
