# Claude Code: what a trial before the go proves

The Chief of Staff's trials (the capability table, `hosts/claude-code.md`):

- An allow rule resolves a matching command at once for the steering session (documented). For a
  Driver a refusal despite a rule exists (`help host-auto-mode`). A trial run where P10 says a
  rule matches proves the host honours that rule's form, which settles the unproved rows (the
  `chantier` launch rules in auto mode, `gh stack*`).
- The host offers no way to try a rule ahead for the commands with no harmless form (`gh release
  create`, `gh pr merge`, `gh api -X PUT .../merge-async`, `gh pr edit --base`, `SendMessage`):
  the classifier judges them at run time. Their only check before the go is P10's rule match.
- A harmless form that the classifier lets through with no rule proves nothing for the real
  command: it judges each command on its own.
- A trial runs in the Chief of Staff's session; a pass there with no rule says nothing about a
  Driver, since the classifier blocks destructive git in subagents.
- Unproved, not documented: `CLAUDE_CODE_ENTRYPOINT` and its values (preflight P1 relies on it
  and it holds in use); the exact text "File has not been read yet" (documented,
  <https://code.claude.com/docs/en/tools-reference>: a Write to an existing file not read first
  fails on older models, newer ones may overwrite under conditions, v2.1.228+); whether a running
  session picks up a change of the settings files (start a new session).
