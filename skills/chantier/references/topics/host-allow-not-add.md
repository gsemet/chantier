# Claude Code: what not to add

Documented (<https://code.claude.com/docs/en/permission-modes>,
<https://code.claude.com/docs/en/auto-mode-config>): auto mode drops on entry, and restores on
leaving, `Bash(*)`, `PowerShell(*)`, interpreter wildcards, package-manager run commands
(`PowerShell(uv run *)`), every `Agent` rule and every `Monitor` rule. So no
`Agent(chantier:cr-driver)` rule is recommended: starting a Driver in auto mode is the
classifier's call. The `Agent(Name)` form is documented; plugin agent names in it
(`chantier:<role>`) are **unproved**.

[Trials](../../../../docs/proofs/claude-code.md#allow-rules)
