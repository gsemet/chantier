# The gaps of a ready-to-merge ask (part 2 of 2)

- The project's rules asking a screenshot of the board pane for a change to it, and a gap naming it missing: ask the user for one screenshot of the pane from a session running the PR's branch, with made-up paths, no username or home folder. A Driver's report that the user's screenshot was not uploaded for showing one: say so and ask for a new one the same way.
- A Driver's `note` or hand-back report (relayed with the ask) saying an image that showed the username or home folder was uploaded and replaced: tell the user the PR, the image and that the old attachment may stay reachable on the forge; nothing more.
- On the user's file: `order note <cr> --note "evidence: <path of the image>"`.
- A stack ask, partial or complete: before you tell the user the stack is mergeable, apply part 1's gap rule to each CR of the mergeable part. Ask for a missing screenshot (made-up paths; tell of an uploaded leak, as above) in the same message, naming the PR and those below and above it, before saying the stack can be merged; the user decides; the evidence route stays.
- A partial ask where the rules ask the stack's top a local run: quote its `local gate <cr> at <sha7>: passed|failed|not run` clause in the user's language before saying the stack can be merged, and say what part 1 says for that result; no clause counts as `not run`.
