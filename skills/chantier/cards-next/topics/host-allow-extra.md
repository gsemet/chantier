# Claude Code: what the base set leaves out

- The base set holds no release, merge or tag rule, by design: a release is rare, public and
  irreversible. When the user grants a release on its own, or fixes on a grant, the Chief of Staff
  offers that capability's rules (the table of `hosts/claude-code.md`), and only then.
- Two rules P10 does not check: `mcp__ccd_pr__set_monitor` (the app's PR monitor; no card uses it,
  to arm or disarm) and `Edit(<folder holding the repository and its worktrees>/**)` (the user's
  path, every file below it).
