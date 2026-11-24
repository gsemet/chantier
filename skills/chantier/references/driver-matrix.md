# CR driver: matrix probe and the board's write paths

## CR driver: matrix probe

A specification that names no host and default matrix ([concepts](concepts.md), "Words") while the
CR plainly depends on the host or on shipped defaults gets one in the evidence plan, written by you.

then, while the CR has
never been pushed and has a matrix, `$CHANTIER phase <cr> verifier matrix probe` and a `verifier`
whose `Note:` says `matrix probe` and gives the matrix (its reply is checked as a Verifier's, with
`Head:` equal to the committed head, but its `Proof:` names `<work folder>/verifier/matrix-r<n>.md`;
no `verify.md` or `verdict` is expected from it), and `$CHANTIER note <cr> "matrix probe
<VERIFIED|NOT VERIFIED> at <sha7>"`: `NOT VERIFIED` is the next round (`$CHANTIER round`, the failed
cells in its brief; past the limit, `blocked rounds:` as for any round), `VERIFIED` goes on,
- when the specification or the evidence plan names a matrix, the checklist also carries
one line per cell from round 1 (the cell, the result it must show, the real flow that proves it),
and the Inspector's prompt carries the whole matrix every round.
- and, with a
matrix, the last `matrix-r<n>.md` as its previous judgment, with the move: the committed head to the
pushed head, the old and new base.

## CR driver: the board's write paths

A CR that touches the board's write paths carries, in each Coder's brief, the scratch-folder rule
of [coder](coder.md); in each Verifier's brief, the `scratch:` folder and the rule of
[verifier](verifier.md) for it (its own repository, every call naming it); and the evidence plan
names the scratch folder each role's runs use.
