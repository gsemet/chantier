# Capability: batch brief

## Purpose

Turn the user's selected, prepared Change Requests into a batch the Foreman can run.

## Who uses it

Chief of Staff.

## Commands

Read `AGENTS.md` and its linked guidelines first. Confirm the selected CRs and grill any open
decisions. Use the existing folder and its complete Change Specification; never replace it with a
raw title. Pass the project's gate commands as shell arguments, one flag per command:

```bash
$CHANTIER open <batch> @<prepared-folder> @<specification-file> \
  --fast-gate "<fast command>" --long-gate "<long command>" \
  [--default-branch <branch>] [--remote <remote>] \
  [--stack] [--slots N] [--budget USD] [--qa all|1,3] [--chief-of-staff <session>]
$CHANTIER status --batch <batch>
$CHANTIER path <cr> --batch <batch> [--spec]
```

For a folder, the default specification is `03-change-spec.md`; `@<specification-file>` selects
another file directly inside the CR folder. Files and folders must be inside the inferred inbox
or priority backlog. The CLI refuses empty or missing specifications, duplicate CRs, missing
gates and an unknown default branch. If the project has one suitable gate for both purposes, pass
it as both flags. Ask the user when a required gate or branch cannot be inferred. The default
remote is `origin`; Git's recorded remote HEAD can supply the default branch.

For a project-specific layout, pass `--inbox`, `--backlog`, `--requests`, `--archives` and
`--trash` for the stages that differ. All paths are project-relative or absolute paths inside
the project. The default changes root is `.agents/changes`; for another root, pass the global
`--changes-dir` before each subcommand, and include its absolute path in every spawn prompt.
Do not assume environment exports survive separate shell calls. If the project's numbering starts
before or after 101,
pass `--first-cr-number <n>`; existing CRs and archives take precedence. Pass other inferred
operational settings such as `--worktrees-dir`, `--max-rounds` and `--stale-minutes` when needed.

`open` moves the entire selected folders into requests, creates worktrees and branches, records
the inferred settings in `batch.json`, and writes a `brief.md` skeleton. Complete the brief from
the grill: selected CRs and QA, mode, slots, budget, project instructions, gates, autonomous
decisions and questions to bring back. Do not add a **Models** override.

## Rules

- The brief is the Foreman's whole mission; never send the mission later by message only.
- Preserve existing CR files; use `$CHANTIER path` after every move instead of assuming a path.
- Agent files must be available before the Foreman starts ([preflight](preflight.md)).

## Failure handling

On a missing convention, invalid CR, collision or failed worktree creation, stop, show the error,
and resolve it with the user before retrying. Never infer that a missing gate passed.
