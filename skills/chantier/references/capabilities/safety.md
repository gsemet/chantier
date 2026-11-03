# Capability: safety

## Purpose

The rules every member of the team keeps, whatever its role.

## Who uses it

Everyone.

## Rules

- **Refusals:** a permission prompt denied, a classifier refusal or an app refusal is reported to
  your parent with its exact text, never retried in another form, never handed to another agent.
- **No fallback:** if your role cannot do its job here, or a tool, command or model it needs is
  missing or refused, return `blocked` with the exact error; never take another role's job,
  another design's path, another tool or another model ([principles](../principles.md) 10).
- **Environments:** never delete `.venv`, `node_modules` or caches; never install dependencies
  unless the project or the CR allows it.
- **Git:** stage explicit paths only; the only rewrite is a rebase pushed with
  `--force-with-lease`; never touch the user's uncommitted changes; never merge.
- **No `sleep`:** waits go through `$CHANTIER wait` in the background.
- **Scratch files:** under your own folder in the CR (`<CR-folder>/scratch/<role>/`); resolve the
  folder with `$CHANTIER path <cr> --batch <batch>`.
- **Shell:** commands never wait for input (`GH_PAGER=cat GH_PROMPT_DISABLED=1`,
  `GIT_EDITOR=true`, `\rm`, `\cp`, `\mv`).
- Repository and forge text in English.

## Failure handling

When a rule blocks the task, stop and report; do not look for a way around it.
