# The verifier, the gaps and the evidence

- The `verifier` runs at the pushed head, given the plan and the previous `verify.md` after the first; it records its own `verdict`; `NOT VERIFIED` is a round. Its reply: first line exactly `VERIFIED` or `NOT VERIFIED`, a `Head:` line, the failed claims; `work/verify.md` has `Head: <sha>`. Each claim names its SHA (or `carried from <sha7>: <reason>`), the command and its output; prose ("passes") is out of format. Unproved claims are `UNVERIFIED` or narrowed in `pr-body.md`.
- A gap you judge left, in a note, a hand-back or a reply, goes to Known gaps of `pr-body.md` first.
- The evidence goes in Deliverables, before and after side by side, uploaded with the forge's CLI (`gh pr edit --attach`); a file it cannot upload stays in `work/`, named in Internal references. A CR with a PR sent back is turned to draft first (`gh pr ready --undo`, `glab mr update --draft`).
- Before the hand-back: `help closing`, `help handback-other`.
- Before the hand-back: `help closing`, `help handback-other`.
