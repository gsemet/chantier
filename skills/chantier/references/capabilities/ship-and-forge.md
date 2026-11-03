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

Use `$CHANTIER path <cr> --batch <batch>` and write the PR body to
`<CR-folder>/pr-body.md` first. Follow the project's commit and PR templates in `AGENTS.md` and
its linked guidance. The CLI currently ships through GitHub (`gh`); do not substitute another
forge when it is unsupported.

## Rules

- One commit per CR in the project's format; explicit paths only.
- Autonomous decisions go in the PR body under "Autonomous decisions".
- `$CHANTIER report <cr> pr-opened <link>` after the first push.
- Never merge.

## Failure handling

Rebase conflict: start a foreground `conflict-resolver`, then `$CHANTIER ship <cr>` again. Push rejected,
or the resolver hands back a product question: `hand-back blocked <reason>`.
