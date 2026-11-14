"""The parser of the `opening` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "open",
        "chantier.commands.opening:open_batch",
        "open a batch: each prepared CR gets its folder, and a branch and worktree name",
        NO_BATCH,
    )
    s.add_argument("items", nargs="+", help="path to a prepared CR folder or specification")
    s.add_argument("--slots", type=int, default=4)
    s.add_argument("--budget", type=float, help="USD; no Driver starts past it")
    s.add_argument(
        "--mode",
        choices=["parallel", "series", "stack"],
        default="parallel",
        help="parallel (default): independent CRs, each on the default branch; series: "
        "one after the other, in the order given, each on the previous one's "
        "branch; stack: independent CRs, then a stack driver stacks the PRs",
    )
    s.add_argument(
        "--release",
        type=int,
        metavar="N",
        help="the item number of the release CR; it waits for every other CR: prepared on top of a "
        "stack or a series once they are ready, after the merges in a parallel batch; its PR "
        "is the user's to merge",
    )
    s.add_argument(
        "--autonomous-releases",
        type=int,
        default=0,
        metavar="N",
        help="releases the user allows without asking (needs --budget)",
    )
    s.add_argument(
        "--grant-fixes",
        action="store_true",
        help="the Foreman starts and merges the release's fixes (needs --budget)",
    )
    s.add_argument(
        "--direct",
        action="store_true",
        help="no Foreman session: the Chief of Staff steers the batch itself",
    )
    s.add_argument("--default-branch", help="default: the remote's HEAD")
    s.add_argument("--remote", default="origin")
