# Claude Code: what stays refused

No allow rule for these; when the host refuses or asks, the agent reports the exact text
(`help refusals-to-say`), and chantier does not do them unasked:

- `git commit --amend --reset-author`: rewrites authorship.
- `git branch -D` with `git push origin --delete`, and `git update-ref -d`: delete refs; a merged
  CR's branch removal (the Foreman's) and a dropped CR's (the Chief of Staff's, on the user's
  word) stay asked, not allowed.
- `Remove-Item -Recurse -Force` or `rm -rf` on `.claude`, or on temporary folders named by a
  wildcard: a pattern can reach what is not chantier's.
- A subagent's Write of a `.md` file whose name starts with `report`, `summary`, `findings` or
  `analysis` (case-insensitive, the file name only): the host refuses it before any permission
  check ("Subagents should return findings as text, not write report files"). The rule is as
  users report it, **unproved** by Anthropic. `04-result.md`, `04-report.md`, `status-layout.md`,
  `delivery.md`, `STATUS.md` and the other chantier names pass: name a subagent's file with a
  number first, such as `04-result.md`.

What not to add: `help host-allow-not-add`.

[Trials](../../../../docs/proofs/claude-code.md#what-stays-refused)
