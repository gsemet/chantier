# Capability: backlog and grill

## Purpose

Keep the project's CR folders and ask only questions that change the result.

## Who uses it

Chief of Staff.

## Commands

Read the project's `AGENTS.md` and its linked guidance before filing. Unless they specify another
layout, use `.agents/changes/backlog/1-inbox/`, `2-backlog/P1…P4/`, `3-requests/`,
`4-archives/`, and `5-trash/` ([definitions](../definitions.md)).

```bash
$CHANTIER file "<raw request>" [--slug <slug>] [--inbox <path>]
$CHANTIER file @<raw-request-file> [--slug <slug>] [--inbox <path>]
$CHANTIER triage <inbox-folder> --priority P1|P2|P3|P4 [--inbox <path>] [--backlog <path>]
$CHANTIER abandon <unclaimed-folder> [--inbox <path>] [--backlog <path>] \
  [--requests <path>] [--archives <path>] [--trash <path>]
```

`file` keeps the supplied request unchanged in `intake/request.md`. Write the intent, capture the
user's answers, and produce the complete Change Specification in that same folder before starting
it. Preserve attachments and other evidence. Triage moves the folder; it does not duplicate it.

The inbox holds ideas: unprioritized requests, possibly rough. The backlog holds the items the
user has prioritized into P1 to P4. The grill is not tied to a stage: question an item and refine
its specification whenever useful, in the inbox, in the backlog, or while the CR is in requests.
Use `abandon` only on the user's explicit decision, never to dispose of a claimed CR.

If the project uses a different changes root, use the global `--changes-dir` before the command.
Pass non-default stage paths from the project guidance. Ask the user when the project convention
cannot be inferred reliably.

## Rules

- File from the user's words and evidence; never invent scope.
- Grill at any stage; before a batch, grill once for all selected CRs that still have open
  questions. Each question carries a recommended answer; skip questions whose answer would not
  change the specification or the brief.
- Triage only on the user's prioritization; never assign P1 to P4 yourself.
- Record every answer in the CR folder. A decision taken without the user goes into the brief and
  later into the PR body.
- Never start a backlog item on your own.

## Failure handling

The user does not answer a blocking question: the CR stays out of the batch; say so.
