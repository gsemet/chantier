# GitLab

The forge reference: the startup cards say "a forge" and name no tool. The mechanism, and how to
add a forge, are in [docs/forge-connectors.md](../../../../docs/forge-connectors.md).

- **Tool:** `glab`, the user's own, logged in by them; the connector's `program`
  (`connectors/gitlab.py`).
- **Its word for a change:** MR (merge request).
- **Used for:** the forge hub reads the MRs a running batch waits for, read-only, every 20 s while
  a client is subscribed (always with `--forge-always`), and needs the network for that. A Driver
  opens the MR and reads its CI with it.
