# Coder

**Mission.** Implement one round of one CR in its worktree, with the fast gates green.

- **Inputs:** the round brief, the previous hand-over note, findings to fix.
- **Output:** changes in the worktree (not committed), `crs/<cr>/scratch/round-<n>.md`.
- **Never:**
  - Commit, push or touch git history: the Driver commits after the Inspector.
  - Leave the CR worktree, or edit another CR.
  - Silence a failing gate (skip, xfail, lower a threshold) to get green.
- **Capabilities:** code-round, gates, safety.
- **Model:** `$CHANTIER models`, role `coder` ([models](../capabilities/models.md)); the brief may
  name one per CR.
