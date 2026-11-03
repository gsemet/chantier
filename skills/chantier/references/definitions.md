# Definitions

Every role uses these words with these meanings only.

## Change Request (CR)

A **Change Request** is a local workspace: one folder that holds everything about one change,
from the request to the specification. By default `$CHANTIER file` creates it in
`<project-root>/.agents/changes/backlog/1-inbox/<slug>/`. The folder moves through the lifecycle;
it is never created inside a batch.

The default stages under `.agents/changes/backlog/` are `1-inbox/`, `2-backlog/P1/` through
`2-backlog/P4/`, `3-requests/`, `4-archives/`, and `5-trash/`. A project may specify different
paths in `AGENTS.md` or its linked guidance. The inbox holds unprioritized ideas; the backlog holds
items the user has prioritized into P1 to P4. The grill can refine a CR at any stage.
Triage moves the folder to a priority; a user-approved
batch moves a prepared CR to requests; a confirmed merge moves it to archives. Dropping it returns
it to its original inbox or priority folder; only explicit abandonment moves it to trash.

Use `$CHANTIER path <cr> --batch <batch>` to find the current folder and add `--spec` to find its
recorded Change Specification. Batch state and the brief live separately in
`<changes>/batches/<batch>/`. Old batches may still point to their original batch-local folders.

Its starting point is the request as it arrived: a request in the prompt, a GitLab issue, a
GitHub issue or a Jira issue.

```text
<slug>/
├── intake/              ← the raw request, as received
├── 01-intent.md         ← the request, summarised and analysed
├── 02-answers.md        ← every answer of the user
├── 03-change-spec.md    ← the Change Specification
└── research/…           ← other files and subfolders, as needed
```

- **`intake/`**: the raw files of the request, kept as received: the prompt text, the issue
  exported from GitLab, GitHub or Jira, its attachments. Never edit them.
- **`01-intent.md`**: the request from `intake/`, summarised and analysed. It names the files of
  `intake/` it comes from.
- **`02-answers.md`**: the user's answers. Every answer the user gives about the CR is written
  here, always, whoever asked the question; an answer that lives only in a chat is lost.
- **Other files**: the CR folder may hold other files and subfolders, for example a `research/`
  subfolder. The CLI may add `task.md`, an initial `STATE.md` and `scratch/` without overwriting
  existing files. The current state is `$CHANTIER status`, not an old `STATE.md` snapshot.

## Change Specification

The **Change Specification** defines what we want to change in the Change Request. By default it
is `03-change-spec.md`; a project may explicitly select another existing file when opening a CR.

It is complete and self-contained: a reader who has only this file knows what to change, without
`intake/`, `01-intent.md` or `02-answers.md`. It repeats what it needs from them instead of
pointing to them.
