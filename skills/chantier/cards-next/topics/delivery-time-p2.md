# Delivery time: the floor of a batch (part 2 of 2)

- A CI run's time comes from the forge, read-only (`gh run list --json`, `glab ci list`); no CI on PRs counts 0, said so. Unreadable: `CI time unknown, not counted`.
- No source for the gate's time: the floor is the depth alone, as levels with the critical path, and the delivery time is unknown: say so and state none; ask nobody and run no gate to measure it.
- Any sentence that tells when work will be done comes from the floor, said with its terms; without it, no time is promised.
