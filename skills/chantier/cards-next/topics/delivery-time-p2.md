# Delivery time: the floor of a batch (part 2 of 2)

- A CI run's time: the latest passed runs on its PRs or default branch, read on the forge, read-only (`gh run list --json`, each run's start and update times; `glab ci list`); no CI on PRs counts 0, said so. Unreadable (no `gh` or `glab`, no rights, no passed run yet): `CI time unknown, not counted`.
- No source for the gate's time: the floor is the depth alone, as levels with the critical path, and the delivery time is unknown: say so and state none; ask nobody and run no gate to measure it.
- Any sentence that tells when work will be done comes from the floor, said with its terms; without it, no time is promised.
- Example (a symbol for the CI time): "lock: 13 gates × 35 min = about 7.6 h; chain: 6 levels × (35 min + <CI> min); at least the larger; critical path: CR-a -> CR-b -> CR-c -> CR-d -> CR-e -> CR-f."
