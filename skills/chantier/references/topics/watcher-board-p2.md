# The board's writes (part 2 of 2)

- "Rescan", "I updated the priorities": read the backlog again (`status`, the dashboard, `next-batch.json`) and say what moved and whether the next batch is declared ready (the board then writes `next-batch.json`: the time and the `3-ready` slugs); with a watcher or the pull path running, only when the user asks. That word decides nothing: still ask before opening a batch.
- An `order add` refused: say its text. Other `board wrote` lines: one line, no tool call.
