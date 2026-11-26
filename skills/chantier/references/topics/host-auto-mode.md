# Claude Code: auto mode and a refusal

- Allow, ask and deny matches resolve at once in auto mode, without the classifier, except
  protected paths, critical-path `rm`/`rmdir` and per-command domains (documented,
  <https://code.claude.com/docs/en/permission-modes>). A subagent may differ: whether the
  classifier judges its command despite a matching rule (a Driver's
  `git -C <worktree> push --force-with-lease -u origin chantier/...`) is **unproved**.
- With no rebase rule set, the classifier may refuse a stack driver's rebase and its force push
  ("Destructive or Unwanted Actions"). P10 names the rebase rules, and a Driver's prompt
  carries a `Rewrites:` line (`concepts.md`, "A Driver's prompt"). Whether that line changes the
  classifier's judgement is **unproved**.
- The labels "Git Destructive" and `claude auto-mode defaults` are documented
  (<https://code.claude.com/docs/en/auto-mode-config>); "Merge Without Review", "Create Public
  Surface" and "Destructive or Unwanted Actions" are **unproved**.
- A refusal is reported with its exact text; a refused force push climbs `help refused-push`. The
  Driver records the refused command and text before its push line, so a refusal on a command a
  rule matches is told from one with no rule.
- A loop, a script or a chain matches no prefix rule, so the classifier judges it alone: one
  command per branch.

[Trials](../../../../docs/proofs/claude-code.md#auto-mode)
