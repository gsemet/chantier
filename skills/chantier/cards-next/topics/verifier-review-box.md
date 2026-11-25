# Verifier: the Review box

The Review box (`Review: approved at <sha7>`) is judged against the Driver's note of the pass, read with `$CHANTIER log <cr>` (complete; `handoff` shows the last ten). A note of an approved pass whose SHA is the box's (the reviewed `head`, the round's `committed as <sha>`, the move's head, or for `carried from <sha7>` that sha7) proves the claim; none, or another SHA, is `NOT VERIFIED`. It proves a review happened, not the code.
