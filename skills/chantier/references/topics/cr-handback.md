# The ready hand-back

- `handback <cr> ready <link>` is refused, one line per cause, without a PR recorded, without a passed long gate and a last verdict `VERIFIED` at the PR's head, when the worktree's head is not the one `ship` recorded, and when the tree is dirty or the branch not pushed at that head: fix the cause, `ship`, run the missing gate or a new `verifier`, hand back again.
- `--no-gate "<rule>"` replaces the long gate check only, never the head, clean, pushed and verdict checks, and only where the project's rules declare none, exempt this CR, or name a pipeline job as the long gate; it quotes the rule (`help handback-gate-draft`).
- Just before it, turn the PR ready (`gh pr ready`, `glab mr update --ready`) if its base is the default branch, then `ship <cr> <link>` again. On another base it stays a draft: `handback <cr> ready <link> draft on <base>: waits for <what>`.
- When the body's Known gaps is not "None", the text ends with `gaps: <gap>; <gap>`, each the first sentence of its bullet as written in the posted body, in order, none added, none missing: `handback <cr> ready <link> gaps: …`, or `… draft on <base>: waits for <what>; gaps: …`, or `handback <cr> ready <link> gaps: <gap> --no-gate "<rule>"`.
- The CLI prints the state the CR is in (ready to merge, PR in draft, ready locally).
- Blocked: `note <cr> "…"` first when your context is ending, then `handback <cr> blocked <reason>`; the forms are in `help handback-other`. Then end: ending frees your slot.
