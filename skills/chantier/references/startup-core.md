# Chantier startup core

This is the mandatory common core. The startup manifest is the single list of
mandatory reads; cards named here are deferred references, not boot material.

Run the official `$CHANTIER` preparation for the selected source and version.
If `$CHANTIER` cannot run (the launch fails: uv or uvx cannot set it up or start
it, or the CLI crashes on start), in either mode, at any
call, report the exact error and stop: no work as the role, no seat,
nothing written in the planning folder, never "without it". Do not upgrade,
reinstall, repair, relaunch another way, or choose another source or tool; retry
once only on a transient network error. A CLI refusal, a command's own error
exit and a host's permission denial keep their handling. The CLI is never a tool
a role works without. A steering session tells the user; a started agent ends
its turn with the error as plain text. Other checks are read-only and block only
the actions whose prerequisite failed; distinguish failed, unavailable, and not
performed.

Permissions are scoped to this session, project, and effect. Subordinates
inherit only role-needed permissions, never merge or publication permission.
Reload does not repeat grants or duplicate services. Report role, project,
checked state, blocked actions and causes, pending permissions, authorized
effects, and evidence limits. Distinguish available, documented, exercised,
server-announced, not tested, and skipped validation. Never invent capacity.

Before an action, read every reference listed for it in the manifest. An
inaccessible indispensable reference blocks that action only.
