"""The forge hub and `chantier watch`.

Every watcher of a planning surface (or a repository) on one machine competes for one OS file
lock in the git folder (`chantier/hub.lock`); the one that holds it is the hub, the only process
that reads the forge, for every project of the surface, at most once every 20 s, and appends the
events it finds to each project's `forge-journal.jsonl`. Each watcher reads only its project's
journal and ends 20 s after the last new event, which wakes its session.

The one test seam: the environment variable `CHANTIER_HUB_TEST_TIMES`, read only by `times.py`,
as `<cycle>:<quiet>` in seconds (for example `0.5:3`), shortens the 20 s cycle and the 20 s quiet
for the scenario. There is no command-line option for them."""
