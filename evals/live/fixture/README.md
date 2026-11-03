# tasks-cli

A small to-do list on the command line. Tasks are kept in `tasks.json` in the current folder, or
in the file `TASKS_FILE` names.

```bash
uv run python -m tasks_cli.cli add "buy milk"
uv run python -m tasks_cli.cli list
uv run python -m tasks_cli.cli done 1
```

## Commands

- `add <title>`: add a task.
- `list`: list the tasks, `[x]` for the done ones.
- `done <id>`: mark a task done.
