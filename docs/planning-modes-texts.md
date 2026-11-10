# Planning modes

Chantier plans in a planning folder, in one of two modes. In-project, the planning folder is .agents/changes/ in the project's repository: the Chief of Staff, the Foreman and the Griller run on the project's main checkout, on its default branch, and each CR's Driver and workers run in a worktree of the project. External, the planning folder is the changes folder of a project in a planning surface, a git repository of its own with one folder per project (project.md, checkout.yml, changes); the surface is always worked on its default branch, and the sessions run in the surface's checkout. The project's clone is used for git only: the Drivers' worktrees are created from it, under the worktrees folder that checkout.yml names. A running batch's own files and the detailed logs stay local. Archives are in the surface's 5-archives and, by the project's setting, in the CR's pull request. Remote, the user's own finding: a remote session cannot start outside a worktree, so the Chief of Staff starts locally and is then put in remote; Grillers may run in worktrees that are never merged and send their files to the Chief of Staff. Outside contributors submit a CR by a pull request on the surface.

## Header

```md
## 🗺️ Planning modes

Same commands, cards and agents in both: only where the planning folder lives changes.
```

## In-project panel

```md
## In-project (the default)

Project repository · main checkout · default branch
🤵 Chief of Staff + Foreman
🔥 Griller, optional
.agents/changes/ the planning folder

Write the planning folder directly, on the default branch.
The folder may stay out of git (the init advice); no archive in the PR.

Worktrees · <repo>.worktrees/<batch>-<cr>
🚜 CR driver, one worktree per CR
🔨 Workers: Coder · Inspector · Verifier · …
starts

Remote (the user's own finding, not a proved trial)
A remote session cannot start outside a worktree, which blocks planning
on the default branch. So: start the Chief of Staff locally (desktop,
no worktree), then put it in remote (Remote Control); reuse it, in direct
mode. Grillers may run in worktrees that are never merged: their files
go to the Chief of Staff, which places them.
```

## External panel

```md
## External (a planning surface)

Planning surface · its own git repository · always its default branch
🤵 Chief of Staff + Foreman
🔥 Griller, optional
changes/ the planning folder

AGENTS.md                the surface's own rules (its sync)
projects/<name>/project.md    remote, archive setting
projects/<name>/checkout.yml repo: · worktrees:
projects/<name>/changes/     1-inbox … 6-trash
A team of 2 to 4, one subject: every change pushed to the default branch, like an Obsidian vault.

Project's clone
git only: git -C <clone>
no session runs in it

Worktrees (checkout.yml)
🚜 CR driver · 🔨 workers
archive in the PR, by the setting
starts

Kept local, and published
Local (ignored by git): the batch's own files (batch.json, events,
STATUS, locks, seat) and the detailed logs (work/gates/, *.log).
Pushed while a CR runs: its documents, reports and evidence.
Archive: the surface's 5-archives/ (with delivery.md) and, by
project.md's setting, a cleaned copy in the CR's PR.
```

## Bottom band

```md
Who runs where, in both modes

On the default branch: the Chief of Staff, the Foreman and the Griller. In-project, the project's main checkout; external, the surface's checkout.
In a worktree: only the project's code: each CR's Driver and workers. A Griller in a never-merged worktree joins no autosync and commits nothing there.
Outside contributors: submit a CR into 1-inbox or 2-backlog only by a pull request on the surface; the maintainer reviews and merges it.
Privacy: a public surface exposes the requests, the grills, the reports and the evidence; you choose its visibility.
Sync: the surface's own rules win; without any, the Chief of Staff commits and pushes after each step that changes it.
Next to a tracker: the planning folder is the tactical, short-term plan; the tracker keeps the strategic, long-term plan.
```
