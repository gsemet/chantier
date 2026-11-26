# A matrix and the board's write paths

- A specification that names no host and default matrix while the CR plainly depends on the host or on shipped defaults gets one in the evidence plan, written by you.
- A matrix gives the checklist one line per cell from round 1 (the cell, the result it must show, the real flow that proves it), and the Inspector's prompt carries the whole matrix every round.
- While the CR has never been pushed and has a matrix: `$CHANTIER phase <cr> verifier matrix probe` and a `verifier` whose `Note:` says `matrix probe` and gives the matrix. Its reply is checked as a Verifier's (`Head:` equal to the committed head), its `Proof:` names `<work folder>/verifier/matrix-r<n>.md`; no `verify.md` or `verdict` is expected. Then `$CHANTIER note <cr> "matrix probe <VERIFIED|NOT VERIFIED> at <sha7>"`: `NOT VERIFIED` is the next round with the failed cells in its brief (past the limit, `blocked rounds:`); `VERIFIED` goes on.
- Later verifiers get the last `matrix-r<n>.md` as the previous judgment, with the move.
- A CR that touches the board's write paths carries, in each Coder's brief, the scratch-folder rule of the coder card; in each Verifier's brief, the `scratch:` folder and the verifier card's rule (its own repository, every call naming it); the evidence plan names the scratch folder each role's runs use.
