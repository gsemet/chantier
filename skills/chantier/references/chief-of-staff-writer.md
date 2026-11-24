# Chief of Staff: the surface's writer

## The surface's writer

The surface's writer ([concepts](concepts.md)) commits and pushes the plan. You never commit the
plan by hand; the surface's other files stay yours to commit, by hand. While a writer runs you
never pull or push the surface by hand: it pushes your hand commits too. On a `writer:` line (of
`status`, `seat`, P13 or `sync`) or a writer's journal line, act as it says:

- **conflict:** in the surface's checkout, `git fetch`, `git rebase origin/<branch>`; resolve each
  file to your best guess, or ask the user; never a force push. The writer pushes once integrated.
- **blocked:** the way out the line gives, else tell the user the reason. Blocked by a stash git
  cannot reapply: tell the user where the edits are, the stash's name the line gives.
- **offline, or late:** tell the user once per episode.
- **not running:** start the surface server ([session-start-chief-of-staff](session-start-chief-of-staff.md), "The board"). When the line
  names an older board, ask the user to stop it with the stop command it gives, then start the
  server.
- **stopped:** tell the user the reason the line gives, once per episode, and restart the
  surface server as for not running.
- A Foreman's `writer off` ask: the same. `$CHANTIER sync now` when a step must reach the forge at
  once.
