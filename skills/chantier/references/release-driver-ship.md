# Release driver: the release PR

## Release driver: the release PR

- In every mode, prepare the release PR (in an ordered batch on top of the stack, its notes
  covering the previous release up to its own head), pass what the procedure names at the pushed
  head, CI green, the body refreshed from the drafts first, as above, then `handback ready <pr
  link>[ draft on <base>]: waits for the merge`. No `blocked merge:`, no verifier. The release PR
  is the user's to merge; the steering session merges it only under the grant. A new Driver goes
  on from the procedure's next step once it is merged. `[foreman→driver <cr>] fix <fix-cr>`:
  `handback blocked fix: <fix-cr> pending`.
- A procedure with no release PR: prepare the drafts (`note --draft`), then `handback blocked
  waits: the other CRs' merge, then the user's word to run the release procedure` (alone: the
  user's word only).
