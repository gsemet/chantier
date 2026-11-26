# GitHub

The forge reference: the startup cards say "a forge" and name no tool. The mechanism, and how to
add a forge, are in [docs/forge-connectors.md](../../../../docs/forge-connectors.md).

- **Tool:** `gh`, the user's own, logged in by them; the connector's `program`
  (`connectors/github.py`).
- **Its word for a change:** PR (pull request).
- **Used for:** the forge hub reads only the PRs a running batch waits for, read-only, every 20 s while
  a client is subscribed (always with `--forge-always`), and needs the network for that. A Driver
  opens the PR and reads its CI with it.
