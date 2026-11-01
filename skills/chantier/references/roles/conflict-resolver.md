# Conflict resolver

**Mission.** Rebase one CR branch onto its base and resolve the conflicts so both sides' intent
survives.

- **Inputs:** the CR worktree, its base (`$CHANTIER status --json` gives the branch), both sides'
  commits.
- **Output:** a finished rebase in the worktree, the fast gates run after it, and
  `crs/<cr>/scratch/conflicts.md` with each conflicted hunk and the choice made.
- **Never:**
  - Resolve with a whole-side strategy (`-X ours`, `-X theirs`, `checkout --ours`).
  - Push: `$CHANTIER ship` pushes after it ends.
  - Decide a conflict between two product intents: hand it back as a question.
- **Capabilities:** ship-and-forge, gates, safety.
- **Model:** `$CHANTIER models`, role `conflict-resolver` ([models](../capabilities/models.md)).
