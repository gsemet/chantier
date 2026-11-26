# Claude Code: the write guard on the shell

Its Bash or PowerShell call is judged the same on the write forms the mod sees with a target: `>`,
`>>`, `tee`, `sed -i`, `perl -i`, `cp`, `mv`, `rm`, `touch`, `truncate`, `Set-Content`,
`Add-Content`, `Out-File`, `Clear-Content`, `New-Item`, `Copy-Item`, `Move-Item`, `Remove-Item`,
`Rename-Item`, `[IO.File]::Write*`. A relative target is read against the agent's folder. A target
outside every folder is refused with `refused: a shell write to <path> is outside the folders ...`.
Passed: a null device, `2>&1`, and `git`, `gh`, `glab` and the chantier CLI.

A guard that cannot judge lets the call pass and says so in the board's note (`Write guard: could
not read ...`): a missing path, a `writes:` entry that is not absolute (the agent is then unguarded
and unmoved), a shell target with a variable or `~` or after a `cd`, `Set-Location` or `pushd`, a
call it cannot parse, its own error. Not guarded: the main sessions, the release, stack and QA drivers, the specification
agents, the Griller, the Demo explorer, any agent with no `writes:` line, and shell writes the mod
cannot see (`python -c`): the card's rule covers them. The host's scratchpad is outside the
worktree; a worker writes in its work folder. Copilot has no guard and the line is inert there.

[Trials](../../../../docs/proofs/claude-code.md#write-guard)
