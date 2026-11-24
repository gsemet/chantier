# Stack driver: the restack pass

## Stack driver: the restack pass

Merged CRs are gone from it, moved to `3-done` at once and alone,
while the stack lives. After a partial merge what remains is a new stack of the same batch, and
one restack for what remains, whatever the number of CRs one merge action of the user merged: on
`origin/<default branch>`, the restack is one planned pass, in this order:
  1. `git -C <main checkout or clone> fetch <remote>` once, then `$CHANTIER stack` once (the old
     heads), before any rebase. The forge may have rewritten the remote branches above the merged
     PR (GitHub's native stack merge did in batch-17): the local branches stay the source of each
     CR's commits, and a `--force-with-lease` push after this fetch replaces the forge's rewrite
     (unproved; trial: the next native stack merge on GitHub, the restack's pushes accepted and
     `forge-stack show` exit 0).
  2. Rebase every remaining CR with no live Driver, bottom up, each on the one under it (the first
     on `origin/<default branch>`), all before any push. A conflict goes the usual way
     (`conflict-resolver`, or "A conflict that needs code").
  3. Push every moved branch right after the last rebase, back to back, once each with
     `--force-with-lease` (a refused one goes up as `driver:refused` says; one command per branch, never a loop or
     a script), so the forge starts every PR's CI at once; then `ship` each one once, bottom up (`--conflict`
     by the rule of the long-gate bullet): `ship` records the new base and the carry. Pushing a branch and waiting for its CI before rebasing the next one is
     what this pass avoids.
  4. One CI wait for all of them (heavy CI once at the top), the proofs each move touched judged
     again as above, then one `$CHANTIER forge-stack rebuild` (no manual retarget: it retargets
     the first PR to the default branch), read back before the hand-back; then the local gate at
     the mergeable top, when its head carries no pass (a clean restack carries it: no run).

This hand-back is silent: no `stack-ready-to-merge` follows
a restack. On GitLab, the forge may already have retargeted the next MR to the default branch when
the merged MR's source branch was deleted: `rebuild` then retargets nothing for it, which is no
anomaly (unproved; trial: one run on a GitLab project). A middle MR merged on GitLab is a folded
CR ([foreman-stack](foreman-stack.md), "A folded CR"; the Foreman's `take` for it comes first). After a restack, `ship` names the lines of
`work/pr-body.md` whose SHA left the head's history (`off: pr-body.md line <n> names …`) and the images (`shows an
image from …`), attached as the evidence bullet says: fix
them (carried, or judged again, as above), post the file (`gh pr edit --body-file`), and run
`ship` again until no such line remains, before the PRs turn ready. A CR added by `order add` is
on top. A CR with an `after` (its dependencies) stands, once `stack` has ordered it, at its place
in the stack, as `take stack` prints, and `stack` refuses an order that puts it below one
of them; a dependency sent back to a Driver is yours to restack. The release CR: restack it like any PR above (rebase onto the CR under it, push with
`--force-with-lease`, `ship`, `--conflict` by the rule of the long-gate bullet), shipped last, after the top CR is shipped at its new head (`ship` refuses it otherwise); its checks run again, and no `verifier` and no `inspector` is
started for it (it has no verdict). The batch stays running until its last CR ends.
