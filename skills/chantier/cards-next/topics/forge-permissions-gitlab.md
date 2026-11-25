# Forge permissions, GitLab

All unproved; trial: one run on a GitLab project. These probes run at step 1 for the capabilities the batch uses.
1. `glab auth status` and the token's scopes (`api` is needed).
2. `glab api projects/<url-encoded path>`: `permissions.project_access` or `group_access` `access_level` 30 or more to push, open MRs and create a release.
3. `glab api projects/<url-encoded path>/protected_branches`: a name or wildcard matching a `chantier/` branch with `allow_force_push: false` refuses the force push; `push_access_levels` above the account's level refuses the push.
4. No native stack: nothing to probe (a stack stays a chain).
5. `glab api projects/<url-encoded path>`: `merge_method`, `approvals_before_merge` or the approval rules, merge trains; `protected_branches/<default branch>`: `merge_access_levels` above the account's refuses the merge.
