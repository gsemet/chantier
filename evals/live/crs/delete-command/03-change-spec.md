# `tasks delete <id>`

## Change

- `tasks delete <id>` removes the task with that id and prints `deleted <id>: <title>`.
- An id that no task has prints `error: no task <id>` and returns exit code 1; the file is left
  unchanged.
- Ids of the other tasks do not change; a later `add` still takes the highest id plus one.

## Done when

- Tests cover deleting an existing task, an unknown id, and the id of a task added afterwards.
- README.md documents the command with an example.
- The fast and long gates pass.
