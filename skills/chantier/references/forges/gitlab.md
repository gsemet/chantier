# GitLab

The reference of the GitLab forge, for the startup cards, which speak of "a forge" and name no
tool. The mechanism, and how to add a forge, are in
[docs/forge-connectors.md](../../../../docs/forge-connectors.md).

- **Command-line tool:** `glab`, the user's own, logged in by them. It is the `program` of the
  connector (`connectors/gitlab.py`).
- **Its word for a change:** MR (merge request).
- **What chantier uses it for:** the surface server's forge hub reads the forge with it, read-only,
  and only the MR (merge request)s a running batch waits for, every 20 s while a client is subscribed (or
  always, with `--forge-always`), and needs the network for that. A Driver opens the MR (merge request) and
  reads its CI with it.
