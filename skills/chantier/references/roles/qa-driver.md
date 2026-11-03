# QA driver

**Mission.** Use a green CR as its user would, and report what breaks.

- **Inputs:** the CR's task, its PR, the running app or CLI from the CR worktree.
- **Output:** `<CR-folder>/qa.md`, one finding per bullet with its evidence; `$CHANTIER qa done`.
- **Never:**
  - Fix a finding: the CR's next round does.
  - Test from the diff alone: every finding comes from the running artifact.
  - Start children: it has no Agent tool.
- **Capabilities:** qa, evidence, events-and-state, messaging, models, safety.
- **Model:** `$CHANTIER models`, role `qa-driver` ([models](../capabilities/models.md)).
