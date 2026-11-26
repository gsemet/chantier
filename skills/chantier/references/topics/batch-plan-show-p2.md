# The plan to show (part 2 of 2)

- An empty batch (a go before any CR is ready) asks the shape too and shows slots, budget, team and who steers; floor and delivery time "none yet: no CR"; no cut.
- A waiver for a stack: offer "one long gate on the top PR only" (lower PRs are ready to merge once CI is green and the Verifier says VERIFIED); on a yes `$CHANTIER order waive stack --note "<the user's words>"`, also during the run; `--note -` withdraws it. A waiver of one CR or of every CR is recorded one CR at a time, `order waive <cr> --note "<the user's words>" --follow-up <folder>`, after filing the CR that runs the long gate on main (`$CHANTIER file`); never a note in a brief.
- Re-read the seat first (`help seat`).
