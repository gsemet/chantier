# Claude Code: what the base set leaves out

- The base set holds no release, merge or tag rule, by design: a release is rare, public and
  irreversible, and the host's check is a second guard. When the user grants a release on its own, or fixes on a grant, the Chief of Staff
  offers that capability's rules (the table of `hosts/claude-code.md`), and only then.
- Two rules P10 does not check. `mcp__ccd_pr__set_monitor`, the app's PR monitor, **unproved**
  here: no card uses it, to arm or disarm; its risk is a session that arms Auto-fix on a PR.
  `Edit(<folder holding the repository and its worktrees>/**)` lets agents edit in the CR
  worktrees next to the repository, at the risk of every file below it (the path is the user's).

[Trials](../../../../docs/proofs/claude-code.md#allow-rules)
