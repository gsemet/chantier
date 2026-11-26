# A mode switch (part 1 of 2)

The Chief of Staff's `order mode --note <mode>`, any mode to any other, on the user's word; the record is already changed, in `status`. No CR already started is stopped, a merged CR never changes (its record, PR, branch and folder), a fix CR stays outside every shape.

In the record, the open CRs of a series or a stack made by the switch are ordered with the CRs already handed back `ready` at the bottom, in the order they became ready, then the others in the batch's order, the chains (`after`) kept. Leaving a stack clears every CR's place in it; each open PR is then moved by its Driver on a rebase note (`rebase: mode <mode>`).

Read the new order from `status`, then by target (the others: part 2).
- To a stack: `help stack` before the first `take stack`. With two CRs or more handed back `ready` with a PR, the first `take stack` forms it (the same `status` line names it; the stack driver orders the CRs from the record's order, rebases and pushes each PR on the one below, puts each PR it moves to draft, `forge-stack create`, turns the mergeable part ready). A `working` CR's Driver gets `[foreman→driver <cr>] note rebase: stacked on <cr below>`; the CRs not started join on top as they get their PR.
