# Routing

Who talks to whom. A message is one line, prefixed by `[sender→receiver]`, in plain words, with
full URLs. The CLI prints the lines that carry state (an order, an ask, a hand-back); the sender
passes them as printed. A lost line loses nothing: the Chief of Staff reads `$CHANTIER asks`,
the Foreman `$CHANTIER status`, a new Driver `$CHANTIER handoff <cr>`.

| From → to | Lines |
| --- | --- |
| Chief of Staff → Foreman | `order O-<k>: …` (printed by `$CHANTIER order`), `ping` |
| Foreman → Chief of Staff | `ready <batch>`, `ask <A-k>: …` (printed by `$CHANTIER asks`), `pong <status line>`, `final <STATUS.md path>`, `push <branch> <expected remote sha> <local sha>` (a Driver's refused force push, passed as it came), `chain <cr> after <cr>: <reason>` (a queued CR the Foreman chains; the Chief of Staff records it at once, without the user's word), `switched to direct mode <batch>: stopped <cr>…\|none` (the answer to `switch to direct mode`) |
| Chief of Staff → Foreman | also `pushed <branch>`, `push failed <branch> <text>`, `push refused <branch>: <reason or git's exact text>` (the CR's fresh Driver then hands back `blocked refused <exact text>`), `checks red <cr> <pr> at <head7>` (a red CI on a PR ready to merge, relayed from a watcher; the Foreman records nothing for it), `chief-of-staff <session id>` (a hand-over: the new Chief of Staff's session), `switch to direct mode` (the Foreman stops its Drivers, answers and stops; see [foreman](foreman.md)) |
| Chief of Staff → Chief of Staff (hand-over) | `your turn, you are the Chief of Staff`; back: `I have the batch` |
| Griller → Chief of Staff | `<slug> specified` (required for a CR marked for the running batch, optional otherwise), `files for <slug>: <paths>` (a Griller in a worktree) |
| Foreman → Driver | `note <text>`, `fix <fix-cr>`, `ping`, `stop` |
| Driver → Foreman | `hand-back ready to merge <link> [<text>]` or `hand-back PR in draft <link> [<text>]` (the word is the CLI's; the text: the PR stays a draft, and why), `hand-back blocked <reason>` (printed by `$CHANTIER handback`), `anomaly <text>`, `pong <step>`, `push <branch> <expected remote sha> <local sha>` |
| QA driver → Foreman | `qa done <folder> <n> findings` |
| Stack driver → Foreman | `hand-back ready to merge <stack link> <cr>=<link>…`, `anomaly <cr> <text>` |

In direct mode the steering session is the Chief of Staff: the rows between the Chief of Staff and
the Foreman do not travel (what it would send itself is not sent; an ask is still recorded with
`$CHANTIER asks`), and a Driver's lines go to the Chief of Staff, keeping the `foreman` prefix of
the steering session's lines.

A host's notice that the Foreman's session ended a turn is not a line of this table. The Chief of
Staff acts on no such notice, except one that shows the Foreman stopped on an error, which it tells
the user in one line ([Claude Code](hosts/claude-code.md), "The Foreman's turn-end notice").

The Chief of Staff's subagents (the Demo explorer, the Spec-writer, the Spec critic) answer the Chief of Staff alone, in their
reply (a Griller's spec critic answers that Griller); they send no line to the Foreman or a Driver.

Grillers send nothing else, to no Foreman and no Driver. The user talks with the Chief of Staff
and with Grillers, about the backlog only in a Griller.

The user talks about a batch only with the Chief of Staff; a Driver's question reaches them as a `blocked
<cr> question: …` ask, and the answer comes back to a new Driver as a note.
