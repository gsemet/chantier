# Claude Code: the allow-rules command line

The Chief of Staff gives it only when the host refused its edit of `~/.claude/settings.json`, or
that file is not JSON (P10 prints `unreadable: ...`); otherwise it adds the rules itself on the
user's yes (`help allow-rules`). **Unproved**.

- **Where:** at the computer running Claude Desktop, not the phone, in your shell.
- **Do:** run the one line for your shell, with the rules P10 named, then start a new session
  (whether a running session picks up a settings change is **unproved**).
- **Paste:** the line; it merges exactly those rules into `permissions.allow`, creating the file
  and keys when absent, keeping every other key and rule, adding none twice, removing nothing, as
  JSON in UTF-8 with no byte-order mark. The Windows line writes compact JSON; a `<` or `'` in
  another value may come back as its `\u` escape.
- **You should see:** `P10 ok` at the next preflight, or a P10 line that no longer names them.

Fill in only the list: the strings P10 named, in table order, `origin` replaced by the project's
remote, `<checkout>` and `<plugin root>` by the real path (the check rule's too), no placeholder. A path holding a `'`
breaks the quoting: say so instead of giving the lines. The shell lines: `help host-allow-add-lines`.
