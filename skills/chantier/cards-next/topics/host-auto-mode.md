# Claude Code: auto mode and a refusal

- Allow, ask and deny matches resolve at once in auto mode, without the classifier, except
  protected paths, critical-path `rm`/`rmdir` and per-command domains (documented,
  <https://code.claude.com/docs/en/permission-modes>). Seen otherwise for a subagent: the
  classifier refused a Driver's `git -C <worktree> push --force-with-lease -u origin chantier/...`
  that an allow rule matched. Whether it judges a subagent's command despite a matching rule is
  **unproved**.
- The classifier refused a stack driver's rebase and its force push when no rebase rule was set
  ("Destructive or Unwanted Actions"). P10 now names the rebase rules, and a Driver's prompt
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
