# Foreman: the retro critic

## The retro critic

**The retro critic.** Draft the points of this pause without writing them (with no point, write
the one untagged line as above; no critic runs). With one point or more, start one `retro-critic`
([`retro-critic.md`](retro-critic.md)), its agent, model and first line copied from `$CHANTIER
playbook --batch <batch>`, and wait for its reply. Its brief numbers the points as drafted and
names, per point, the evidence it cites (the CRs' `work/` notes, `events.jsonl`, `4-batch/STATUS.md`,
`cost --explain` when a point rests on a cost): never your argument for a point, your ranking or
your preference. When a release CR is done in `4-batch/3-done/` and its `work/retro.md` has not yet
been through a critic, its points go in the same brief, numbered after yours; that file stays as the
release Driver wrote it. Write the section with the kept points only, each as drafted (a merge: one
line covering both; a kept release point is written in the section, marked `(release)`), under the
same header, which then ends with `(critic: kept <k>, dropped <d>)`. With every point dropped, the
section holds one untagged line: `- nothing worth changing (critic: <d> points dropped)`. Write the
dropped and merged points, each with the critic's one-line why, in `4-batch/retro-dropped.md` (a
section per pause, headed like the retro's): it is not the record, `close` deletes it, so a dropped
point leaves no trace after the close. Follow the verdicts as given: never keep a dropped point nor
drop a kept one. If the critic ends early or answers out of format, restart it once; if it fails
again, write no point in `retro.md` but the one line `- retro not checked: <cause>`, keep your
drafted points in `retro-dropped.md`, and say so in your `final`. The critic's run counts in the
batch's cost; it comes after the pause and before `final`. The same critic checks any other list of changes
you propose on your own (a suggestion in an answer to the user), before you give it; a change the
user asked for does not go through it.
