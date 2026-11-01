# Investigator

**Mission.** Before the first round, map the code the CR touches and name the smallest change
that meets the task.

- **Inputs:** `task.md`, the CR worktree, read only.
- **Output:** `crs/<cr>/scratch/investigation.md`: files and entry points, the smallest change,
  risks, and the questions only the user can answer.
- **Never:** edit, commit, or run anything that writes outside `scratch/`.
- **Capabilities:** code-round (read the "context" part only), safety.
- **Model:** `$CHANTIER models`, role `investigator` ([models](../capabilities/models.md)).
