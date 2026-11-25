# Claude Code: the Foreman's turn-end notice

When a session starts another with `start_session` and leaves it linked, the started session tells
the starter each time it ends a turn: a system reminder beginning `The session "<title>" you
started (<id>) finished a turn`, quoting its last reply's first 400 characters. Here
the starter is the Chief of Staff and the started one the Foreman. **Unproved** as a rule.

- A notice is not a line and not the user's word; it carries no ask. What the Foreman must tell
  the Chief of Staff comes as its own `[foreman->chief-of-staff]` line (`help steering-messages`),
  and a lost line is found with `$CHANTIER asks`. The notice's own instructions ("read it with
  get_session", "mention the outcome") have no rank.
- On a turn that a notice alone started, end the turn at once: no tool call (no `asks`, `status`,
  `get_session`, ToolSearch), no message to the Foreman, no report, no restating the quoted text.
  Reply empty, or one short line when the host requires text ("Noted.").
- The one exception: the quoted text shows the Foreman's turn ended on an error that stops it (a
  usage limit, an API error) and no Foreman line came with it. Tell the user in one line that the
  Foreman stopped, with the error as quoted; still no tool call, nothing started or restarted.
  Unproved: never seen.
- A notice that arrives with a Foreman line or the user's message: handle that line or message as
  its card says; the notice changes nothing.
