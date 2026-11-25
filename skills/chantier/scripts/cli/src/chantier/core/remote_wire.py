"""What the client and the server's `cli.run` agree on: the environment names a command may carry,
the commands that never run remotely, and how the options a profile takes over (`--profile`,
`--project`, `--skill`) are found in a command line, in their two forms and their argparse
prefixes, judged with the CLI's own parser."""

from __future__ import annotations

import argparse

# The only environment a client sends; one constant for both sides. `CHANTIER_VIA_SERVER` is
# never in it: only the server sets it.
FORWARDED_ENV = (
    "CHANTIER_BATCH",
    "CHANTIER_HOST",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_ENTRYPOINT",
    "COPILOT_AGENT_SESSION_ID",
    "COPILOT_CLI",
    "AI_AGENT",
)
VIA_SERVER = "CHANTIER_VIA_SERVER"
TAKEN_OVER = ("--profile", "--project", "--skill")
# Commands that run where they are typed, whatever the profile: they never reach the server, and
# the server refuses them.
NEVER_REMOTE = ("serve", "watch", "webui", "live", "login", "logout", "gate", "push")


def options_of(parser: argparse.ArgumentParser, cmd: str | None) -> list[str]:
    """Every long option the root parser and the command's parser know."""
    found = [o for a in parser._actions for o in a.option_strings if o.startswith("--")]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) and cmd in action.choices:
            sub = action.choices[cmd]
            found += [o for a in sub._actions for o in a.option_strings if o.startswith("--")]
    return found


def taken_over(token: str, known: list[str]) -> str | None:
    """The option among `TAKEN_OVER` that `token` (`--opt`, `--opt=value`, or a prefix of the
    name) stands for, as argparse resolves it; None for any other token."""
    if not token.startswith("--") or token == "--":
        return None
    name = token.split("=", 1)[0]
    if name in known:
        return name if name in TAKEN_OVER else None
    matches = {o for o in known if o.startswith(name)}
    return matches.pop() if len(matches) == 1 and matches <= set(TAKEN_OVER) else None


def strip(argv: list[str], parser: argparse.ArgumentParser, cmd: str | None) -> list[str]:
    """The command line with the options a profile takes over removed, with their values, before
    or after the command; what follows a bare `--` stays."""
    known = options_of(parser, cmd)
    out: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--":
            return out + argv[i:]
        if taken_over(token, known):
            i += 1 if "=" in token else 2
            continue
        out.append(token)
        i += 1
    return out


def holds_taken_over(argv: list[str], parser: argparse.ArgumentParser, cmd: str | None) -> str:
    """The first option of `argv` that stands for `--profile`, `--project` or `--skill`; empty
    for none."""
    known = options_of(parser, cmd)
    for token in argv:
        if token == "--":
            break
        if found := taken_over(token, known):
            return found
    return ""
