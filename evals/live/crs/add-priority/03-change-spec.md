# Add a priority to tasks

## Change

- `tasks add <title> --priority low|normal|high`; default `normal`. Any other value is refused by
  argparse with exit code 2.
- Each task stores `"priority"`. Tasks saved before this change have no `priority` and count as
  `normal`.
- `tasks list` prints ` (low)` or ` (high)` after the title; nothing for `normal`:
  `[ ] 3: buy milk (high)`.

## Done when

- Tests cover the default, each explicit value, a refused value and an old task without priority.
- README.md documents the option with an example.
- The fast and long gates pass.
