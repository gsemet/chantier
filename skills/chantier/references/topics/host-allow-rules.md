# Claude Code: how allow rules match

Table and block to paste: `hosts/claude-code.md`. Documented
(<https://code.claude.com/docs/en/permissions>):

- `*` matches anywhere; `cmd *` (with a space) is a word boundary and also matches bare `cmd`.
- `Bash(git push ...)` does not match `git -C <path> push ...`: the `-C` form needs its own rule.
- `PowerShell(...)` rules have the Bash shape, are case-insensitive, aliases canonicalized.
- A compound command passes only when every part is allowed (Bash: `&&`, `||`, `;`, `|`, `&`,
  newline; PowerShell: `|`, `;`, and from PowerShell 7 `&&`, `||`).
- A Bash allow rule does not match past a leading assignment (`X=1 cmd`), but for known-safe
  variables (deny and ask rules do). PowerShell assignments (`$w='...'; cmd`): **unproved**.
- `mcp__<server>__<tool>` is an exact tool name, a bare tool name all its uses.
  `Edit(~/path/**)` (`~` the home folder, `**` as in gitignore) covers Write and NotebookEdit
  (<https://code.claude.com/docs/en/tools-reference>).
- Order: managed > command line > local > project > user; deny > ask > allow (a user deny
  blocks a project allow).

P10 asks whether some allow rule lets through each command the cards make agents write; a
narrower or other rule of the user's counts when it matches the same commands.

The launcher rule, `launcher_rule(root)`: `uv run --script "<plugin root>/skills/chantier/scripts/chantier.py" *`.
**Unproved** (matching, auto mode, a Driver).
