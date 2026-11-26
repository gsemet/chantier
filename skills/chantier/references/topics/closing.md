# The closing

Below 115,000 tokens on the last `context:` line you read, carry it out yourself, one note as each step ends (a fresh Driver resumes at the first step with no note):
1. Evidence in Deliverables and the Test plan boxes updated (SHAs as in the PR template; a claim the Verifier could not prove is `UNVERIFIED` or narrowed in `pr-body.md` first), the pre-post audit, the post (`gh pr edit --body-file`): `closing: body posted at <sha7>`.
2. A short `verifier` pass on the posted description alone (`NOT VERIFIED` is fixed in the description, then a new short `verifier` start, never a message to the one that replied): `closing: description pass VERIFIED at <sha7>`.
3. The PR ready when its base is the default branch, `closing: PR ready` (a PR that stays draft: `closing: PR kept draft on <base>`), then `ship <cr> <link>`.
4. `handback ready <pr link>` with the gaps the body's Known gaps hold.

The one note after `VERIFIED` (unless the log holds a `closing: VERIFIED at` note): `closing: VERIFIED at <sha7>; PR <link>; base <branch>; pr-body.md posted at <sha7 or not yet>; evidence: <files verify.md names>; UNVERIFIED: <claims or none>; next: <the steps>`. A matrix probe's `VERIFIED` and a verdict carried by `ship` need none.

At 115,000 tokens or more, or `context: not measured`, hand off: `handback <cr> blocked context: closing: VERIFIED at <sha7>; next: <what is left>`, and end; a fresh Driver starts with `resume: closing`. This hand-off needs no `context:` line at 130,000. During the closing, at 130,000 or when the host asks: `blocked context: closing: <last step done>; next: <what is left>`.

The last edit of the PR body comes before the description pass; any later edit runs the pass again before the PR turns ready, never in the same command, except, after a carried verdict, the edit that only changes SHA marks to `at <head7> (carried from <sha7>)`.
