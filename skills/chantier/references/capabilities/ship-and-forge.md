# Capability: ship and forge

## Purpose

Commit, rebase, push and open or update the PR for an external reader.

## Who uses it

CR Driver, stack driver.

## Commands

```bash
$CHANTIER ship <cr>        # rebase on the fresh default branch (in a stack: on the CR below), push
                      # with lease, open or update the PR; a conflict aborts the rebase, exit 4
```

Write the PR body to `crs/<cr>/pr-body.md` first. Templates and forge commands:
[pr-body.md](../../../change-request-factory/references/pr-body.md), [commits.md](../../../change-request-factory/references/commits.md),
[forge-github.md](../../../change-request-factory/references/forge-github.md), [forge-gitlab.md](../../../change-request-factory/references/forge-gitlab.md).

## Rules

- One commit per CR in the project's format; explicit paths only.
- Autonomous decisions go in the PR body under "Autonomous decisions".
- `$CHANTIER report <cr> pr-opened <link>` after the first push.
- Never merge.

## Failure handling

Rebase conflict: start a foreground `conflict-resolver`, then `$CHANTIER ship <cr>` again. Push rejected,
or the resolver hands back a product question: `hand-back blocked <reason>`.
