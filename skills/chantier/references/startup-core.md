# Chantier startup core

This is the mandatory common core. The startup manifest is the single list of
mandatory reads; cards named here are deferred references, not boot material.

Run the official `$CHANTIER` preparation for the selected source and version.
If it fails, report its exact diagnostic and stop role initialization: do not
upgrade, substitute, repair, or choose another source or tool. Other checks
are read-only and block only the actions whose prerequisite failed; distinguish
failed, unavailable, and not performed.

Permissions are scoped to this session, project, and effect. Subordinates
inherit only role-needed permissions, never merge or publication permission.
Reload does not repeat grants or duplicate services. Report role, project,
checked state, blocked actions and causes, pending permissions, authorized
effects, and evidence limits. Distinguish available, documented, exercised,
server-announced, not tested, and skipped validation. Never invent capacity.

Before an action, read every reference listed for it in the manifest. An
inaccessible indispensable reference blocks that action only.
