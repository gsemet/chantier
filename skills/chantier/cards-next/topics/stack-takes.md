# The stack grows: the other takes

- In the same turn as each `take stack`, for each row it printed `not on its place`: `[foreman→driver <cr>] note rebase: stacked on <cr below>` (the row's `base`). Never hold the take for it.
- The final-order take, once every non-release CR has handed back (`ready` or `blocked`), none `working`, none `queued` that could start (one whose dependency is blocked or cancelled stays out), before `take <release>`: `take stack --note "final order" --epoch <n>` (a running stack driver gets `[foreman→stack] note final order`, after its current work); beside it goes the one-time ask for a cancelled dependency. It may move any CR (one linear native stack). A CR that goes back to a Driver afterwards makes it due again once it hands back. The ask that follows names each queued CR left out, with its unmet dependency.
- A parked CR is out of the stack (`help park`): `take stack --note "park: <cr>"`.
