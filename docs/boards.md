# Boards

The CR board in Claude Code, a read-only pane over the planning folder, and the web board, served by `chantier board` to any device on the local network.

## The CR board (Claude Code)

### What it is

A Claude Code mod (early access): a read-only pane over the planning folder's `STATUS.json` (one
section per project in a surface). It shows the live batches, the backlog (and `3-ready`), and the
merged and trashed CRs. Nothing of it on Copilot, and the pane is not shown in a Remote Control view
([anthropics/claude-code#99217](https://github.com/anthropics/claude-code/issues/99217)). It writes
nothing and runs no process but `git rev-parse`, to find the main checkout from a worktree.

### How to open it

`/chantier-board` shows or hides it. Loading the `chantier` or `chief-of-staff` skill opens it too
(not `griller`).

### How to read it

At the top, a header line: `5 live · 0 waiting for you · checked 3s ago, every 15 s`: when the pane last checked, and its period. Under it, each batch has a
line (its id, its cost against its budget, a gauge), its unread asks and its slots (`Slots 3/3, 0
free`). Then "Waiting for you" and "In progress", with the columns CR, Subject, State, PR and Cost.
The state says the state, the step and the round: `working Round 1/3`, `working CI 2/3`,
`ready Notify 1/3`, `queued`. Then Backlog, Merged (n of m) and Trashed (n of m). Press a CR for its
sheet and its documents. The pane checks every 15 seconds while open and reads a file again only when it changed. A **Refresh** button at the top of the pane (in every view) checks at once: it reads the files again, even unchanged ones, and looks for the planning folders again (a project added to a surface, a `.agents/changes/` created after opening), keeping the page shown and the folds. It does not refresh the batch's cost or record: that moves when the steering session refreshes the status.

### A batch in pictures

A batch just opened: three CRs working in round 1/3, two queued, no PR yet, no cost.

![The board, a batch just opened](board-mod-batch.png)

Three CRs in CI, with PRs #1 to #3 and their costs: $0.57 of $20.

![The board, three CRs in CI with their PRs](board-mod-batch-prs-light.png)

"3 waiting for you": two CRs ready, and one unread ask.

![The board, three things waiting for you](board-mod-waiting-light.png)

"Merged (2 of 2)" open.

![The board, the merged CRs](board-mod-merged-light.png)

The batch done: 0 live, $9.22 of $20, and "Merged (5 of 5)" with each CR's PR and cost.

![The board, the batch done](board-mod-batch-done.png)

### Two facts the pictures raise

They are not bugs.

- The header's "waiting for you" counts the unread asks as well as the table's rows: in the
  merged picture, "1 waiting for you" sits beside "Nothing waits for you".
- The batch's cost is priced when the steering session refreshes the status, not live: $0.57 over
  three pictures while the CRs moved on, then $9.22 once the batch was done.

### The guard of a worker's and a CR Driver's writes

The same mod starts an agent whose prompt holds a `writes:` line in its first folder (a worker's:
its worktree; a CR Driver's: its CR folder) and refuses its Write, Edit or NotebookEdit outside the
folders named. It judges the agent's Bash or PowerShell writes the same way when it can see them (a
redirection, `Set-Content`, `sed -i`, `rm`...); what it cannot see, such as an interpreter's inline
code, is covered by the cards, and the steering session reports what changed in the main checkout.

## The web board

On any device, the Chief of Staff starts a small web server, `chantier board`, that serves the
batch with its CRs (state, round, cost, PR), the inbox, `3-ready` and the backlog, the merged and
trashed CRs, the costs, and each CR's files (text and images). It stops when its session leaves
the seat. It writes in the backlog only (the inbox, the priorities, `3-ready`), never in a batch:
file an idea, move items between those places, label and group them, edit an item's Markdown
files, and declare the next batch ready (`next-batch.json`, the time and the CRs then in
`3-ready`; it decides nothing). Every write lands in `board-journal.jsonl` (not committed); the
"rescan" button empties it, to tell the Chief of Staff the backlog changed. All projects is
read-only.

- **The link.** The Chief of Staff gives you one link, `http://<address>:8765/?k=<key>`. Open it
  once: the board keeps the key in a cookie and takes it out of the address. The link is yours
  only; whoever has it reads the planning folder. `chantier board --new-key` replaces the key
  and the old link stops working. The key lives in the repository's git folder
  (`chantier/board.json`), so it survives restarts and is never pushed.
- **The local network.** By default the board listens on every address of the machine
  (`0.0.0.0`): your phone on the same network reaches it. It speaks plain HTTP, so keep the link
  off any network you do not trust. On Windows, the first start asks the firewall for permission:
  that prompt is the machine's own.
- **Keeping it on the machine.** Set the address once in `chantier.yaml` (on your word, the Chief
  of Staff writes it):

```yaml
board:
  host: 127.0.0.1   # only this machine; default 0.0.0.0, the local network
  port: 8765        # default 8765
```

- **By hand.** `chantier board --host <address> --port <n>`. With no plugin and no agent, on a
  machine where only `uv` is installed, start it from a planning surface with
  `uvx --from git+https://github.com/gsemet/chantier@v<version> chantier --project <folder> board`
  (`<version>` is the release the surface's planners use).
- **When it stops.** With Ctrl-C, or by itself once no session that registered a seat holds it any
  more. A second `chantier board` on the same address says the board is already running and
  prints the same link.