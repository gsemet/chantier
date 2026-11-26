# The orders (part 2 of 2)

- `order merged <cr>`: the user merged its PR, to `3-done`
- `order slots --note <n>`: 0 holds, a number resumes
- `order rounds <cr> --note <n>`: on the user's word, or under the rounds exception (`help rounds-exception`)
- `order budget --note <usd>`
- `order mode --note parallel|series|stack`: any mode to any other, on the user's word
- `order qa --note "<what to test>"`: a QA driver on the project's head; takes a slot
- `order waive stack --note "<the user's words>"`: a stack, one long gate on the top PR only; `order waive <cr> --note "<the user's words>" --follow-up <backlog folder>`; `--note -` withdraws it (the stack's, or a CR's own)
- `order approve <release-cr> --note "<the action>"`
- `order grant <release-cr> --note "releases=<n> fixes=on|off budget=<usd>"`
- `order confirm <release-cr> --note "<the user's word to run the release procedure>"`, once the other CRs are merged
