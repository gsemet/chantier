# Claude Code: sessions of one repository

All unproved until the session tool is recorded.

- The seat: liveness is asked of the host (the Tools row), never read from a date; where the host
  cannot tell, the session asks the user (the "looks stopped" line).
- A fork: what it inherits, whether it has its own session id (`$CLAUDE_CODE_SESSION_ID`) and
  whether anything tells it it is a fork are unknown. Trial: fork a Chief of Staff session, compare
  `get_session("self")` and the variable with the seat. With its own id, the next comparison with
  the seat makes it a Griller; without, a fork cannot be told apart and the user says "you are a
  griller" in it.
- A Griller in a worktree sends its files by `SendMessage` to the seat's session, naming absolute
  paths; the Chief of Staff on the main checkout reads them under `.claude/worktrees/<name>/`.
- The two-Chiefs case and hand-over lines travel by `SendMessage` like the rest.
- Claude Desktop limits messages between sessions (10 since someone last typed): a refused send is
  reported, never sent another way. It applies to the lines between a Griller and the Chief of
  Staff and to a hand-over's.
