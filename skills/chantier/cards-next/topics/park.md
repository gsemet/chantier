# Parking a CR on an outside wait

A CR whose work waits on an outside step (the user's trial or answer, an approval, an outside pipeline or merge) is parked at once, with no question once the wait is recorded.
- Working, its Driver says it waits: `park <cr> --wait ... --epoch <n>`, its Driver stopped, `agents set <cr> - --epoch <n>`.
- Handed back `blocked` with such a wait (`question:`, `approval:`, `waits:` with a typed `--wait`): `park <cr> --epoch <n>`, then `agents set <cr> - --epoch <n>` when `park` prints it. In a stack, `take stack --note "park: <cr>"`.
- Send the line `park` printed: `[foreman→chief-of-staff] parked <cr>: ...`. Trouble in the work (`fix:`, `infra:`, `rounds:`, `context:`, `refused`) is not parked.
- A working dependent (a series successor already started included) keeps its Driver; its PR stays a draft and is not merged before the parked CR is back.
Back, a drop with dependents: `help park-back`.
