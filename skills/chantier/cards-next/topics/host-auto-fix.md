# Claude Code: Auto-fix events

Auto-fix is a Claude Desktop feature: the app binds a PR a subagent opened to the session that
started it (the Foreman, or the Chief of Staff in direct mode) and sends it events (fix failing
checks, merge the base in). **Unproved** as a rule until a real
campaign shows it.

- An event is not an order: neither the user's word nor a batch line. The project's rules, then
  the cards, rank above it. A CR's branch is brought up to date the project's way (a rebase),
  never by the base merge the event asks for.
- A CR with a live Driver (`working`, its Driver recorded): do nothing on the PR (no fix, merge,
  rebase, push, no relay to the Driver) and end the turn. The Driver reads its own CI and holds the
  branch; a relay costs messages against the host's limit.
- A CR with no live Driver (`ready`, `blocked`, waiting): the event is a signal. Check the forge
  (`gh pr checks`, `gh pr view --json mergeable`, `glab`). Really red or in conflict: the usual
  route, `take <cr> --note "<why>"` (`help take-back`). Nothing wrong: nothing is done. Never do
  what the event asks yourself.
- Both steerings follow this; a PR that is not a batch's is out of chantier's rule.
- Chantier never arms, disarms or unbinds the PR monitor (`mcp__ccd_pr__set_monitor`) and writes
  no setting of it; it stays silent about Auto-fix (no preflight, no "For you" line). The per-PR switch is documented; a global one is **unproved**.
