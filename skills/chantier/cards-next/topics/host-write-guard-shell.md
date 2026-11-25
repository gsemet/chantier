# Claude Code: the write guard on the shell

Its Bash or PowerShell call is judged the same on the write forms the mod sees with a target: `>`,
`>>`, `tee`, `sed -i`, `cp`, `mv`, `rm`, `touch`, `Set-Content`, `Out-File`, `New-Item`,
`Copy-Item`, `Remove-Item` and the like. A target outside every folder is refused with `refused: a
shell write to <path> is outside the folders ...`. Passed: a null device, `2>&1`, and `git`, `gh`,
`glab` and the chantier CLI.

A guard that cannot judge lets the call pass and says so in the board's note (`Write guard: could
not read ...`). Not guarded: the main sessions, the release, stack and QA drivers, the specification
agents, the Griller, the Demo explorer, any agent with no `writes:` line, and shell writes the mod
cannot see (`python -c`): the card's rule covers them. The host's scratchpad is outside the
worktree; a worker writes in its work folder. Copilot has no guard and the line is inert there.
