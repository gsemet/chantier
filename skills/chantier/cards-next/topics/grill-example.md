# A series, worked

One item (`ready-wording`, CR-<n> <slug>), two questions. The text written first:

```text
ready-wording-Q1 - Which words open the ready line?
Context: CR-<n> <slug>. The line is the first thing the user reads after a batch.
A. Name the CR first (recommended). Example: "CR-<n> <slug>: PR <m> ready".
B. Name the PR first. Example: "PR <m> ready (CR-<n> <slug>)".
C. Count first. Example: "3 of 4 ready: CR-<n> ...".
Recommendation: A, the CR is what the user knows; "Other" is there for anything else.

ready-wording-Q2 - Does the line quote the known gaps?
Context: CR-<n> <slug>. Gaps decide whether the user merges.
A. Yes, quote them (recommended). Example: "... PR <m> ready, gap: no screenshot".
B. No, link the PR only. Example: "... PR <m> ready".
Recommendation: A, a gap left out is a surprise at the merge.
```

Then the tool call, the short mirror (same references, order and first words):

```text
AskUserQuestion
  ready-wording-Q1: A. Name the CR first (recommended) | B. Name the PR first | C. Count first
  ready-wording-Q2: A. Yes, quote them (recommended) | B. No, link the PR only
```
