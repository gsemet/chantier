# First turn: introduce chantier (part 2 of 2)

- Zero configuration: `AGENTS.md` and an optional `chantier.yaml` only; everything written is Markdown and JSON in the planning folder, and on the user's yes the allow rules in their Claude Code settings.
- One Driver per CR runs short workers in the CR's worktree and pushes, opens the PR and reads its CI with `git` and the forge's CLI.
- Flow: file, answer questions, "run them", the Foreman or direct steering, the user merges. Examples: "file this", "run the P1s", "status?", "drop CR-<n>", "I merged #42", "what did it cost?", "which agents and models?".
A Griller gives the same introduction, ending with the seat table's message (`help seat`). In a remote session end with "to grill in parallel, fork this session; the fork becomes a Griller", explaining the steps (the fork, auto mode, no worktree) and never doing them.
