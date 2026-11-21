"""The commands the cards make the agents write and the allow rules that cover them (the table of
hosts/claude-code.md), with the chantier rows' placeholders and how they are filled."""

from __future__ import annotations

from pathlib import Path

from chantier.launch import (
    dev_launch,
    dev_rule,
    plugin_launch,
    plugin_rule,
    sync_check_line,
    sync_check_rule,
    sync_line,
    sync_rule,
)
from chantier.plugin_files import skill_dir

# The commands the cards make the agents write, filled with realistic values, each tied to the
# recommended allow rule that covers it and to a group. P10 asks whether some allow rule of the
# user's settings lets each one through (as Claude Code matches rules), whatever the rule's form.
_SHA = "0123456789abcdef0123456789abcdef01234567"


_BRANCH = "chantier/batch-01/cr-101-example"


_TREE = "/work/project.worktrees/batch-01-CR-101"


# The placeholders of the three chantier rows: the host card shows them, P10 fills them with this
# install's real paths from the functions of `plugin_files` (the one source of the launch text).
CHECKOUT = Path("<checkout>")
PLUGIN_ROOT = Path("<plugin root>")
_PLUGIN_SKILL = Path("<plugin root>/skills/chantier")


# (capability, forge, command, recommended rule); ` origin ` stands for the project's remote name.
# The capability is one of CAPABILITIES; the forge is any, github, gitlab, gh-stack, dev or plugin.
# The order is the order of the table "Capabilities and their commands" in hosts/claude-code.md;
# SendMessage, a bare tool, belongs to the capability batch and comes last.
# P10 counts these commands, not rules.
SAMPLES = (
    ("batch", "any", f"git push -u origin {_BRANCH}", "git push -u origin chantier/*"),
    (
        "batch",
        "any",
        f"git -C {_TREE} push -u origin {_BRANCH}",
        "git -C * push -u origin chantier/*",
    ),
    (
        "batch",
        "any",
        f"git push --force-with-lease -u origin {_BRANCH}",
        "git push --force-with-lease -u origin chantier/*",
    ),
    (
        "batch",
        "any",
        f"git -C {_TREE} push --force-with-lease -u origin {_BRANCH}",
        "git -C * push --force-with-lease -u origin chantier/*",
    ),
    (
        "batch",
        "any",
        f"git push --force-with-lease={_BRANCH}:{_SHA} origin {_SHA}:refs/heads/{_BRANCH}",
        "git push --force-with-lease=chantier/* origin *chantier/*",
    ),
    (
        "batch",
        "any",
        f"git -C {_TREE} push --force-with-lease={_BRANCH}:{_SHA} "
        f"origin {_SHA}:refs/heads/{_BRANCH}",
        "git -C * push --force-with-lease=chantier/* origin *chantier/*",
    ),
    (
        "batch",
        "dev",
        f"{dev_launch(CHECKOUT)} status",
        dev_rule(CHECKOUT),
    ),
    (
        "batch",
        "dev",
        sync_line(CHECKOUT),
        sync_rule(CHECKOUT),
    ),
    (
        "batch",
        "dev",
        sync_check_line(CHECKOUT),
        sync_check_rule(CHECKOUT),
    ),
    (
        "batch",
        "plugin",
        f"{plugin_launch(PLUGIN_ROOT, _PLUGIN_SKILL)} status",
        plugin_rule(PLUGIN_ROOT),
    ),
    ("batch", "github", "gh pr create --draft --body-file /tmp/body.md", "gh pr create*"),
    ("batch", "github", "gh pr edit 12 --body-file /tmp/body.md", "gh pr edit*"),
    ("batch", "github", "gh pr edit 12 --base chantier/batch-01/cr-100-base", "gh pr edit*"),
    ("batch", "github", "gh pr ready 12", "gh pr ready*"),
    ("batch", "github", "gh pr ready 12 --undo", "gh pr ready*"),
    ("batch", "github", "gh pr checks 12", "gh pr checks*"),
    ("batch", "github", "gh pr view 12", "gh pr view*"),
    ("batch", "github", "gh pr close 12", "gh pr close*"),
    ("batch", "github", "gh pr reopen 12", "gh pr reopen*"),
    ("stack", "gh-stack", "gh stack view", "gh stack*"),
    (
        "batch",
        "gitlab",
        "glab mr create --draft --description-file /tmp/body.md",
        "glab mr create*",
    ),
    ("batch", "gitlab", "glab mr update 12 --target-branch main", "glab mr update*"),
    ("batch", "gitlab", "glab mr view 12", "glab mr view*"),
    ("batch", "gitlab", "glab mr close 12", "glab mr close*"),
    ("batch", "gitlab", "glab mr reopen 12", "glab mr reopen*"),
    ("batch", "gitlab", "glab ci status", "glab ci status*"),
    ("release", "github", "gh pr merge 12 --rebase", "gh pr merge*"),
    (
        "release",
        "github",
        "gh api -X GET repos/o/r/stacks -F per_page=100",
        "gh api -X GET repos/*/stacks*",
    ),
    (
        "release",
        "github",
        "gh api -X PUT repos/o/r/pulls/12/merge-async -f merge_method=rebase "
        f"-f merge_action=direct_merge -f sha={_SHA}",
        "gh api -X PUT repos/*/pulls/*/merge-async*",
    ),
    (
        "release",
        "github",
        "gh api -X GET repos/o/r/pulls/12/merge-async/0a1b2c3d-4e5f-6789-abcd-ef0123456789",
        "gh api -X GET repos/*/pulls/*/merge-async/*",
    ),
    ("release", "gitlab", "glab mr merge 12 --rebase", "glab mr merge*"),
    ("release", "any", "git push origin v1.2.3", "git push origin v*"),
    (
        "release",
        "github",
        "gh release create v1.2.3 --verify-tag --notes-file /tmp/notes.md",
        "gh release create*",
    ),
    (
        "release",
        "gitlab",
        "glab release create v1.2.3 --notes-file /tmp/notes.md",
        "glab release create*",
    ),
    ("fixes", "github", "gh pr merge 12 --rebase", "gh pr merge*"),
    (
        "fixes",
        "github",
        "gh api -X GET repos/o/r/stacks -F per_page=100",
        "gh api -X GET repos/*/stacks*",
    ),
    (
        "fixes",
        "github",
        "gh api -X PUT repos/o/r/pulls/12/merge-async -f merge_method=rebase "
        f"-f merge_action=direct_merge -f sha={_SHA}",
        "gh api -X PUT repos/*/pulls/*/merge-async*",
    ),
    (
        "fixes",
        "github",
        "gh api -X GET repos/o/r/pulls/12/merge-async/0a1b2c3d-4e5f-6789-abcd-ef0123456789",
        "gh api -X GET repos/*/pulls/*/merge-async/*",
    ),
    ("fixes", "gitlab", "glab mr merge 12 --rebase", "glab mr merge*"),
)


# The capabilities, in the table's order, and how P10 names each.
CAPABILITIES = {
    "batch": "every batch",
    "stack": "a stack",
    "release": "a release on its own",
    "fixes": "fixes on a grant",
}


def _allow_for(capabilities: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        f"{tool}({rule})"
        for rule in dict.fromkeys(s[3] for s in SAMPLES if s[0] in capabilities)
        for tool in ("Bash", "PowerShell")
    )


# The allow rules hosts/claude-code.md recommends, in its table's order (a test compares them):
# the capabilities every batch and a stack; the pasteable block holds exactly these.
RECOMMENDED_ALLOW = (*_allow_for(("batch", "stack")), "SendMessage")


def filled_allow() -> tuple[str, ...]:
    """`RECOMMENDED_ALLOW` filled for this install: the checkout's or plugin's real path in the
    three chantier rules (the scenario and the tests use it)."""
    return tuple(fill_rule(rule) for rule in RECOMMENDED_ALLOW)


def fill_rule(rule: str) -> str:
    """A rule with its placeholder (`<checkout>`, `<plugin root>`) filled for this install, by
    `plugin_files`' rule functions; any other rule unchanged."""
    root = skill_dir().parents[1]
    for tool in ("Bash", "PowerShell"):
        for held, filled in (
            (dev_rule(CHECKOUT), dev_rule(root)),
            (sync_rule(CHECKOUT), sync_rule(root)),
            (sync_check_rule(CHECKOUT), sync_check_rule(root)),
            (plugin_rule(PLUGIN_ROOT), plugin_rule(root)),
        ):
            if rule == f"{tool}({held})":
                return f"{tool}({filled})"
    return rule


def fill_sample(sample: tuple[str, str, str, str]) -> tuple[str, str, str, str]:
    """A sample with its placeholders filled: the exact launch plus ` status`, the exact sync
    and check lines, and the filled rule; any other sample unchanged."""
    cap, forge, _command, rule = sample
    root = skill_dir().parents[1]
    if rule == plugin_rule(PLUGIN_ROOT):
        return cap, forge, f"{plugin_launch(root, skill_dir())} status", plugin_rule(root)
    if rule == dev_rule(CHECKOUT):
        return cap, forge, f"{dev_launch(root)} status", dev_rule(root)
    if rule == sync_rule(CHECKOUT):
        return cap, forge, sync_line(root), sync_rule(root)
    if rule == sync_check_rule(CHECKOUT):
        return cap, forge, sync_check_line(root), sync_check_rule(root)
    return sample


# The rules offered only under a grant (a release on its own, fixes on a grant): not in the block.
GRANT_ALLOW = _allow_for(("release", "fixes"))
