# Routing

Who talks to whom. A message is one line, prefixed by `[sender→receiver]`, in plain words, with
full URLs. The CLI prints the lines that carry state (an order, an ask, a hand-back); the sender
passes them as printed. A lost line loses nothing: the Chief of Staff reads `$CHANTIER asks`,
the Foreman `$CHANTIER status`, a new Driver `$CHANTIER handoff <cr>`.

| From → to | Lines |
| --- | --- |
| Chief of Staff → Foreman | `order O-<k>: …` (printed by `$CHANTIER order`), `ping` |
| Foreman → Chief of Staff | `ready <batch>`, `ask <A-k>: …` (printed by `$CHANTIER asks`), `pong <status line>`, `final <STATUS.md path>`, `push <branch> <expected remote sha> <local sha>` (a Driver's refused force push, passed as it came) |
| Chief of Staff → Foreman | also `pushed <branch>`, `push failed <branch> <text>`, `push refused <branch>: <reason or git's exact text>` (the Driver then ends with `handback blocked refused <exact text>`) |
| Foreman → Driver | `note <text>` (the push result too), `fix <fix-cr>`, `ping`, `stop` |
| Driver → Foreman | `hand-back ready <link>`, `hand-back blocked <reason>` (printed by `$CHANTIER handback`), `anomaly <text>`, `pong <step>`, `push <branch> <expected remote sha> <local sha>` |
| QA driver → Foreman | `qa done <folder> <n> findings` |
| Stack driver → Foreman | `hand-back ready <cr>=<link>…`, `anomaly <cr> <text>` |

The user talks only with the Chief of Staff; a Driver's question reaches them as a `blocked
<cr> question: …` ask, and the answer comes back to a new Driver as a note.
