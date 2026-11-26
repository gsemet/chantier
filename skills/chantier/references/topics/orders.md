# Orders

Orders are the user's word. `status` lists them until you mark each `order done`: `orders pending` holds those nothing has touched (a note, a QA, the drop of a live CR); another line holds those the CLI applied, which await only your `order done`. `pause` waits for both. Their effect on the state is applied; what needs your hands is yours: stop a Driver, tell one, send a CR handed back to a Driver with `--note` saying why (its Driver turns the PR back to a draft).
- `order rounds`: when the CR then holds a note starting `rounds exception:` (`status`'s order list, `handoff <cr>`, `log <cr>`), `take <cr> --note "rounds exception: <cause>"`, no escalation, and mark the order done only after the `take`. Without such a note: `escalate: rounds` (`help escalation`).
- A dropped live CR: `cancel <cr> --epoch <n>` moves it to the destination its drop order recorded; you never choose one. A `cancel` refused for a missing destination goes up as an ask. Then `help drop`.
- An order note `evidence: <path>` (the user's screenshot of the board pane) becomes `take <cr> --note "evidence: <path>"`.
- A refusal you do not understand: `access <cr> --epoch <n>` explains it and changes nothing.
The queue and an order that adds work: `help orders-queue`. The Chief of Staff's: `help order-verbs`.
