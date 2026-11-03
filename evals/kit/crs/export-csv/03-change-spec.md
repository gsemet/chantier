# `tasks export --csv <file>`

## Change

- `tasks export --csv <file>` writes the tasks to `<file>` as CSV: UTF-8, comma-separated, one
  header row, one row per task in id order, and prints `exported <n> tasks to <file>`.
- **Columns: to be decided by the user.** The Driver asks the user which columns (and in which
  order) before round 1, and the round's brief uses the answer.

## Done when

- Tests cover an export of two tasks and of no task (header only).
- README.md documents the command with an example.
- The fast and long gates pass.
