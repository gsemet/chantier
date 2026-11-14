# Routing

Who talks to whom. A message is one line, prefixed by `[sender→receiver]`, in plain words, with
full URLs. The CLI prints the lines that carry state (an order, an ask, a hand-back); the sender
passes them as printed. A lost line loses nothing: the Chief of Staff reads `$CHANTIER asks`,
the Foreman `$CHANTIER status`, a new Driver `$CHANTIER handoff <cr>`.

| From → to | Lines |
| --- | --- |
| Chief of Staff → Foreman | `order O-<k>: …` (printed by `$CHANTIER order`), `ping` |
| Foreman → Chief of Staff | `ready <batch>`, `ask <A-k>: …` (printed by `$CHANTIER asks`), `pong <status line>`, `final <STATUS.md path>`, `push <branch> <expected remote sha> <local sha>` (a Driver's refused force push, passed as it came), `chain <cr> after <cr>: <reason>` (a queued CR the Foreman chains; the Chief of Staff records it at once, without the user's word) |
| Chief of Staff → Foreman | also `pushed <branch>`, `push failed <branch> <text>`, `push refused <branch>: <reason or git's exact text>` (the Driver then ends with `handback blocked refused <exact text>`), `chief-of-staff <session id>` (a hand-over: the new Chief of Staff's session) |
| Chief of Staff → Chief of Staff (hand-over) | `your turn, you are the Chief of Staff`; back: `I have the batch` |
| Griller → Chief of Staff | `<slug> specified` (optional), `files for <slug>: <paths>` (a Griller in a worktree) |
| Foreman → Driver | `note <text>` (the push result too), `fix <fix-cr>`, `ping`, `stop` |
| Driver → Foreman | `hand-back ready <link> [<text>]` (the text: the PR stays a draft, and why), `hand-back blocked <reason>` (printed by `$CHANTIER handback`), `anomaly <text>`, `pong <step>`, `push <branch> <expected remote sha> <local sha>` |
| QA driver → Foreman | `qa done <folder> <n> findings` |
| Stack driver → Foreman | `hand-back ready <stack link> <cr>=<link>…`, `anomaly <cr> <text>` |

In direct mode the steering session is the Chief of Staff: the rows between the Chief of Staff and
the Foreman do not travel (what it would send itself is not sent; an ask is still recorded with
`$CHANTIER asks`), and a Driver's lines go to the Chief of Staff, keeping the `foreman` prefix of
the steering session's lines.

The Chief of Staff's subagents (the Demo explorer, the Spec-writer, the Spec critic) answer the Chief of Staff alone, in their
reply (a Griller's spec critic answers that Griller); they send no line to the Foreman or a Driver.

Grillers send nothing else, to no Foreman and no Driver. The user talks with the Chief of Staff
and with Grillers, about the backlog only in a Griller.

The user talks about a batch only with the Chief of Staff; a Driver's question reaches them as a `blocked
<cr> question: …` ask, and the answer comes back to a new Driver as a note.
