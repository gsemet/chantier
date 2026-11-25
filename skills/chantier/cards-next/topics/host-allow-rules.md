# Claude Code: how allow rules match

The table and the block to paste are in `hosts/claude-code.md`. Documented
(<https://code.claude.com/docs/en/permissions>):

- `*` matches anywhere; `cmd *` (with a space) is a word boundary and also matches bare `cmd`.
- `Bash(git push ...)` does not match `git -C <path> push ...`: the `-C` form needs its own rule.
- `PowerShell(...)` rules have the Bash shape, are case-insensitive, aliases canonicalized.
- A compound command passes only when every part is allowed.
- A Bash allow rule does not match past a leading assignment (`X=1 cmd`); for PowerShell
  assignments (`$w='...'; cmd`) that is **unproved**.
- `mcp__<server>__<tool>` is an exact tool name; an `Edit(~/path/**)` rule covers Write.
- Precedence: managed > command line > local > project > user; deny > ask > allow.

P10 holds the commands the cards make agents write and asks whether some allow rule lets each
through: a narrower or different rule of the user's counts when it matches the same commands.

The launcher rule, `launcher_rule(root)`: `uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" *`,
the one `$CHANTIER` form of both modes. **Unproved** as a rule (matching, and its fate in auto mode
and in a Driver); trial: set it, run `$CHANTIER status` in auto mode, see whether the classifier is
asked.
