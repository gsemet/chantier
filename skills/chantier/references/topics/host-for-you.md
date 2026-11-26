# The "For you" block, on Claude Code

Whenever a step is the user's, give one block in the user's language, always four parts, the cost
first when the choice has one: **Where** (device and app), **Do** (each choice by its label on
screen, in order), **Paste** (the text in its own code block, complete, no placeholder left),
**You should see** (what comes next and within how long; else say what you see). Every block is
**unproved**: say "I have not tested this path".

- **A new Foreman**, desktop or remote: nothing for the user; `start_session` as the Tools row says.
  The user only gives the go.
- **A planning surface's project folders** (unproved: a Driver creating a worktree from the clone
  in a surface session): Do: add the project's clone and its worktrees folder as working
  directories (`/add-dir <path>`, or `additionalDirectories` in `.claude/settings.json`); Paste:
  the two absolute paths `checkout.yml` resolves to; See: the Driver's `git worktree add` and commit
  accepted, else tell me the refusal as written.
- **`/compact`**: type it in the session and send; a summary and a smaller context follow within
  a minute.

A reused Foreman and a session on the main checkout: `help host-for-you-sessions`.

[Trials](../../../../docs/proofs/claude-code.md#other-the-for-you-block)
