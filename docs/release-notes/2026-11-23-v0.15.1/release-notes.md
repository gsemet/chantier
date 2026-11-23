<h1 align="center">chantier 0.15.1</h1>

<p align="center"><b>Fix preflight when you work from the project's checkout beside the planning surface, and stop a missing clone from crashing the permissions check</b></p>

<p align="center"><sub>3 changes since 0.15.0 · Claude Code and GitHub Copilot · MIT</sub></p>

<p align="center">
<a href="https://github.com/gsemet/chantier#install">Install</a> ·
<a href="https://github.com/gsemet/chantier/blob/v0.15.1/docs/tutorial-claude-code.md">Tutorial</a> ·
<a href="https://github.com/gsemet/chantier/blob/v0.15.1/docs/use-cases.md">Use cases</a> ·
<a href="https://github.com/gsemet/chantier/compare/v0.15.0...v0.15.1">Full changes</a>
</p>

---

## 🛫 Start a session from the project's checkout, with the plan kept elsewhere

With the plan in an external planning surface, `preflight` used to refuse a session opened in the project's own checkout. It now accepts the main checkout of the surface or of the project's clone, and still refuses a linked worktree of either. The checks that concern a folder (the surface's default branch, the forge remotes, the settings files) read that folder, not the one the process happens to run in.

<img src="preflight-pc.png" alt="chantier preflight in the main checkout beside the planning surface: P6, P7, P8, P11 and P13 ok, preflight passed">

## 🛠 Smaller changes

- **A missing clone no longer crashes the permissions check.** The git reads of the allow-rule check are skipped when the project's clone is missing, so the other lines still print; `preflight` reports the missing clone itself.
- **The release procedure is named in the project's instructions.** The `AGENTS.md` section for chantier points at it.

<details><summary><b>🐞 All fixes</b></summary>

- **Preflight.** The project's checkout is accepted as the session folder beside the planning surface; a linked worktree is still refused.
- **Permissions.** A missing project clone no longer raises in the allow-rule check and drops the other lines.

</details>

<details><summary><b>🛠 For contributors</b></summary>

- **Not exercised by an eval.** No eval ran for this release. Both fixes are proved by the tests, and neither came up in an eval run:
  - the session folder accepted beside the planning surface (proved by the tests);
  - the permissions check that skips its remote reads when the clone is missing (proved by the tests).
- The release's claims file is `evals/results/claims-v0.15.1.md`: one row per change, its rail and its result.

</details>
