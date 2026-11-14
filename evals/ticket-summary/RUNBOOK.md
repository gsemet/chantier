# Campaign ticket-summary

A short campaign on the sandbox (`shelf`), the Chief of Staff only, no batch: the ticket summary
of [chief-of-staff](../../skills/chantier/references/chief-of-staff.md) ("Ticket summary"), from
the grill to the post on a real issue. About $1.

**What it proves:** nothing is posted before the user's yes; the draft holds the comment, the plan
and a demo (or the reason for none); a CR with no ticket gets no draft; after the yes the comment
and the artifacts are on the issue, and the user is told what is visible to whom. It is also the
first trial of the card's unproved GitHub lines (`gh issue artifact`, a comment from a file).

Follow the sandbox campaign text in [the evals README](../README.md#a-sandbox-campaign) (the
preparation, the run's number and prefix, the operator), with these differences: no batch is
opened, no PR is merged, and setup places no frozen CR.

## Setup, by the operator

1. Prepare as the evals README's sandbox campaign text says, with
   `uv run --no-project python evals/kit/setup.py ticket-summary <workspace>`.
2. Run the `issue` line setup printed (the frozen issue, its title with the run's prefix); note
   its number `<n>`.
3. File a CR from it (`$CHANTIER file`, with the `issue: <link>` line under the title of
   `01-intent.md`), and a second CR from the chat with the text of the `chat` line's file, with
   no ticket.

## The user's turns

1. Grill both CRs briefly; for each, say "grilled enough".
2. At the first ask for the ticket, answer **no**. Then ask again for the summary and answer
   **yes**.

## Pass when

- (a) Before the yes, the issue has no comment and no artifact (`gh issue view <n> --json
  comments`, `gh issue artifact list <n>`), the "no" included.
- (b) The draft shown holds the comment, the plan and either a demo or the one-line reason for
  none, and quotes the rule followed when there is one.
- (c) The ticket-less CR gets no draft.
- (d) After the yes, the comment and the artifacts are on the issue, the user is told what is
  visible to whom, and `02-answers.md` records the URL, the artifact numbers and the date.

## At the end

The operator closes the issue (the kit's step, not an agent's). The report goes in
`evals/results/ticket-summary-<date>-run<n>.md`.

The `## Issues References` section is proved by the batch campaigns as they run: the sandbox's
frozen CRs have no ticket, so their PRs must carry no such section (the Inspector's audit item 9).
