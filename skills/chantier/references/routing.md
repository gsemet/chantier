# Routing

Who talks to whom. A message is one line, prefixed by `[sender→receiver]`, in plain words, with
full URLs. The CLI prints the lines that carry state (an order, an ask, a hand-back); the sender
passes them as printed. A lost line loses nothing: the Chief of Staff reads `$CHANTIER asks`,
the Foreman `$CHANTIER status`, a new Driver `$CHANTIER handoff <cr>`.

| From → to | Lines |
| --- | --- |
| Chief of Staff → Foreman | `order O-<k>: …` (printed by `$CHANTIER order`), `ping` |
| Foreman → Chief of Staff | `ready <batch>`, `ask <A-k>: …` (printed by `$CHANTIER asks`), `pong <status line>`, `final <STATUS.md path>` |
| Foreman → Driver | `note <text>`, `fix <fix-cr>`, `ping`, `stop` |
| Driver → Foreman | `hand-back ready <link>`, `hand-back blocked <reason>` (printed by `$CHANTIER handback`), `anomaly <text>`, `pong <step>` |
| QA driver → Foreman | `qa done <cr> <n> findings` (printed by `$CHANTIER qa`) |
| Stack driver → Foreman | `hand-back ready <cr>=<link>…`, `anomaly <cr> <text>` |

The user talks only with the Chief of Staff; a Driver's question reaches them as a `blocked
<cr> question: …` ask, and the answer comes back to a new Driver as a note.
