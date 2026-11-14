# The demo planning surface

A fictional planning surface, kept in the repository for one purpose: `just docs-screenshots`
copies it to a temporary folder, starts the web board on the copy and takes the screenshots of
`docs/web-board/`. Nothing else reads it.

- It is **not** a planning folder of this repository: chantier's own planning is `.agents/changes/`.
  This folder has no `.agents/changes/` and the CLI never discovers it from the repository's root.
- Everything in it is made up: the shop, its people, its pull requests (`example` URLs that no
  screenshot follows) and its dates (the capture fixes the clock at `2026-06-18T10:30:00Z`).
- It is a multi-project planning surface, as [planning-modes](../planning-modes.md) describes:
  `projects/<name>/` with `project.md`, `checkout.yml` and `changes/`.

| Project | What it shows |
| --- | --- |
| `shop-api` | a batch running in stack mode, with every state a CR can be in; an inbox, a backlog from P1 to P4 (P3 left empty), `3-ready`, a CR with sub-folders |
| `mobile-app` | no batch running; an inbox; the last merged CRs in `5-archives/` |
| `docs-portal` | a small project, for the "All projects" table |

The record files a running batch keeps (`batch.json`, `events.jsonl`, `seat.json`) are kept here
too, in the format the server reads. The capture script adds what git does not hold: it initialises
a git repository in its copy and writes the autosync tool's state files there (a group waiting for
an approval), so that the board's pill has a fixed state to draw.
