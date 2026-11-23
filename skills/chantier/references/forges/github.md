# GitHub

The reference of the GitHub forge, for the startup cards, which speak of "a forge" and name no
tool. The mechanism, and how to add a forge, are in
[docs/forge-connectors.md](../../../../docs/forge-connectors.md).

- **Command-line tool:** `gh`, the user's own, logged in by them. It is the `program` of the
  connector (`connectors/github.py`).
- **Its word for a change:** PR (pull request).
- **What chantier uses it for:** the surface server's forge hub reads the forge with it, read-only,
  and only the PR (pull request)s a running batch waits for, every 20 s while a client is subscribed (or
  always, with `--forge-always`), and needs the network for that. A Driver opens the PR (pull request) and
  reads its CI with it.
