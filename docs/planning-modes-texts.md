# Planning modes: in-project and external

Chantier plans in a planning folder, in one of two modes. In-project, the planning folder is .agents/changes/ in the project's repository: the Chief of Staff, the Foreman and the Griller run on the project's main checkout, on its default branch, and each CR's Driver and workers run in a worktree of the project. External, the planning folder is the changes folder of a project in a planning surface, a git repository of its own with one folder per project (project.md, checkout.yml, changes); the surface is always worked on its default branch, and the sessions run in the surface's checkout. The project's clone is used for git only: the Drivers' worktrees are created from it, under the worktrees folder that checkout.yml names. A running batch's own files and the detailed logs stay local. In a planning surface, the surface server commits and pushes the plan. Archives are in the surface's 5-archives and, by the project's setting, in the CR's pull request. Remote: a session the Chief of Staff starts from remote with no cwd and no preset lands in its own main checkout (proved 2026-11-20), so the Chief of Staff starts locally and is then put in remote; from there its batches stay direct, a forced foreman starts the Foreman in its own folder, and Grillers start the same way. A session you create from the remote client lands in a worktree (batch-06). Outside contributors submit a CR by a pull request on the surface.

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

Remote (a start with no cwd, proved 2026-11-20)
A session started from remote with no cwd lands in the Chief of Staff's
own main checkout. So: start the Chief of Staff locally (desktop, no
worktree), then put it in remote (Remote Control). Its batches stay
direct; a forced foreman starts the Foreman in its own folder, and a
Griller starts the same way.
```

## External panel

```md
## External (a planning surface)

Planning surface · its own git repository · always its default branch
🤵 Chief of Staff + Foreman
🔥 Griller, optional
changes/ the planning folder

AGENTS.md                the surface's own rules
projects/<name>/project.md    remote, archive setting
projects/<name>/checkout.yml repo: · worktrees:
projects/<name>/changes/     1-inbox … 6-trash
A team of 2 to 4, one subject: the surface server pushes every change within 5 minutes.

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
In a worktree: only the project's code: each CR's Driver and workers. A Griller in a never-merged worktree commits nothing there.
Outside contributors: submit a CR into 1-inbox or 2-backlog only by a pull request on the surface; the maintainer reviews and merges it.
Privacy: a public surface exposes the requests, the grills, the reports and the evidence; you choose its visibility.
Sync: the surface server's writer pushes the plan; nobody pulls or pushes the surface by hand while it runs.
Next to a tracker: the planning folder is the tactical, short-term plan; the tracker keeps the strategic, long-term plan.
```
