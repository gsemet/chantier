# Boards

The CR board in Claude Code and the remote board, two read-only views of the planning folder.

## The CR board (Claude Code)

`/chantier-board` shows or hides the **CR board**, a read-only pane over
the planning folder's `STATUS.json` (one section per project in a surface): the live batches with what waits for you and what is in
progress, the backlog (and `3-ready`), and the merged and trashed CRs. Each live batch shows its slots
(`Slots 2/4, 2 free`). Press a CR for its sheet and its documents.
Loading the `chantier` or `chief-of-staff` skill opens it too (not `griller`). It refreshes every 15 seconds while open, writes
nothing, and runs no process but `git rev-parse` to find the main checkout from a worktree. It is
a Claude Code mod (early access): nothing of it on Copilot. The pane shows on the machine running
the session, not in a Remote Control view
([anthropics/claude-code#99217](https://github.com/anthropics/claude-code/issues/99217)).
The same mod starts an agent whose prompt holds a `writes:` line in its first folder and refuses
its Write, Edit or NotebookEdit outside the folders named; a shell write is not guarded: the
steering session reports what changed in the main checkout.

## The remote board

In remote there is no pane, so the Chief of Staff also starts a small web page, `chantier board`,
that shows the same view: the batch with its CRs (state, round, cost, PR), the inbox, `3-ready`
and the backlog, the last merged and trashed CRs, and each CR's files as text. It reloads
itself every 30 seconds, is **read only** (to act, you talk to the Chief of Staff), writes no file
and stops when its session leaves the seat. It listens on `127.0.0.1:8765` by default, so only the
machine itself reaches it. To open it from your phone, set the address once in `chantier.yaml`
(on your word, the Chief of Staff writes it):

```yaml
board:
  host: 0.0.0.0   # or the machine's Tailscale address; default 127.0.0.1
  port: 8765      # default 8765
```

Reach it over your private network: Tailscale (the tailnet's address) or your LAN (`0.0.0.0`
listens on every network of the machine). **There is no password**: the Chief of Staff tells you
the address and that fact when the board listens beyond the machine. You can also run it by hand:
`chantier board --host <address> --port <n>`.
