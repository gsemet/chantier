# The tour's checks: gates and long-gate settings

- Check the project's rules declare a fast gate (after every round and before the CR's first push) and a long gate (once before the PR; `handback ready` requires it), or no long gate, or exemptions. A missing one: propose the exact lines, for example "- Fast gate (after each change): `<cmd>`." and "- Long gate (before a pull request): `<cmd>`.", one command per item, never chained with `&&` or `;`. Impact: a long gate the Driver cannot run is a `--no-gate` the steering session must question.
- An extra pre-push line ("- Before the first push, for a change under `src/`: `<cmd>`.") only for a check too slow for every round and too important to leave to CI.
- With a long gate declared or proposed, ask once whether it is isolated per worktree (own ports, temporary folders, services). Yes: ask how many runs at once the machine carries, and propose `long_gate:` / `parallel: <n>` for `chantier.yaml`, written only on the user's yes. No: propose `parallel: 1`. Not asked when `long_gate.parallel` is set (a `long_gate:` holding only `commands` is still asked). Impact when missing: long gates run one at a time and CRs wait their turns.
- On the same yes, propose the `long_gate.commands` entry (a name and the gate's command) for the code repository's root `chantier.yaml`: it makes the gate runnable (`gate <cr> <name>`; `docs/gates.md`). Write it, with the inbox CR offered, as `help project-rules` says.

More: `help init-tools`.
