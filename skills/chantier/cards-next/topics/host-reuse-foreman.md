# Claude Code: reusing the last Foreman

When the previous batch's Foreman session still exists, even stopped, the Chief of Staff may reuse
it with the new batch and its epoch 1 (a new batch starts at 0): it does not continue the old
epoch. Its title names the old batch, so the prompt's title makes it rename itself.

- An idle session answers a message (`SendMessage`): **proved**.
- `foreman set --epoch 1` accepted in a reused session: **proved**.
- A session whose process has ended (closed): **unproved**. The docs do not say a message reaches
  it; they describe waking it by the user's reply. Trial: close a Foreman session, message it from
  the Chief of Staff, see whether a turn starts. Never tell the user a message wakes a closed one.

Say the cost first: a new session starts with an empty context; a reused Foreman carries its old
context, and the batch pays for it. Before a reuse, recommend `/compact` in the Foreman's session,
never `/clear`.
