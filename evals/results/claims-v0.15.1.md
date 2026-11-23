# Claims of v0.15.1

Since v0.15.0, at 8fc641e (origin/main). Runs: none.

No eval ran for this release (the user's word: the fix and the patch release run on their own). A claim that a named check of `just scenario` or `just test` proves is `scenario only`; its evidence names the test files that the commit changed. Every other claim is `not exercised`.

| Claim | Commit | Rail | Can come up in | Result | Evidence |
| --- | --- | --- | --- | --- | --- |
| Accept the project's checkout as the session folder beside the planning surface | d54f2236 | none: no row for preflight | no campaign | scenario only | test_session_folder.py, test_store_reads.py |
| Skip the remote reads of the permissions check when the project's clone is missing | 8fc641ee | none: no row for preflight | no campaign | scenario only | test_session_folder.py |
