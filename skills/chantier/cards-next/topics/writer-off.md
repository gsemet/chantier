# The surface's writer

With a planning surface its writer commits, pulls and pushes it, never you.
- A `writer:` line in `conflict` or `blocked`: `$CHANTIER asks "writer <state>: <reason>"`, once per episode.
- `writer: not running` or `writer: stopped: <why>`: `$CHANTIER asks "writer off"`, once per episode, and no `take` until a `writer:` line in another state comes back, which ends the episode.
