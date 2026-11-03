# `tasks list --json`

## Change

- `tasks list --json` prints the tasks as a JSON array, exactly the objects stored in the tasks
  file, indented by 2 spaces, followed by a newline. With no task it prints `[]`.
- Without `--json`, `list` is unchanged.

## Done when

- Tests cover an empty list and a list of two tasks (one done) in JSON.
- README.md documents the option with an example.
- The fast and long gates pass.

## QA notes

Run the CLI from the worktree with a fresh `TASKS_FILE`: add two tasks, mark one done, check that
`list --json` is valid JSON (`python -m json.tool`) and matches `list`.
