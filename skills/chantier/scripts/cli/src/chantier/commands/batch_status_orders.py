"""What `status` prints about the orders, the stack driver and a Driver's end, moved out of
`batch_status.py` to keep each file at most 400 lines."""

from __future__ import annotations

from chantier.commands.cost.sessions import foreman_uuid
from chantier.core import leases
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord, OrderRecord
from chantier.core.repo import Repo
from chantier.status.due import order_words


def ended_unrecorded(repo: Repo, d: BatchRecord, agent: str | None) -> bool:
    """Claude: the Driver's last tool call is the host's hand-back, yet the CR is still working."""
    from chantier.costs.sessions import agent_handed_back  # noqa: PLC0415 - slow import

    if not agent or d.host == "copilot":
        return False
    try:
        sessions = foreman_uuid(d)
    except ChantierError:
        return False
    return agent_handed_back(repo.session_root, sessions, agent) is True


def order_lines(d: BatchRecord, repo: Repo) -> list[str]:
    open_orders = [o for o in d.orders if not o.done]
    lines = []
    for applied, head in (
        (False, "orders pending: "),
        (True, "orders the CLI applied, the Foreman marks each `order done <O-k> --epoch <n>`: "),
    ):
        group = [o for o in open_orders if bool(o.applied) is applied]
        if group:
            lines.append(
                head
                + "; ".join(
                    order_words(o)
                    + f"{' follow-up ' + o.follow_up if o.follow_up else ''}"
                    + _late_suffix(repo, o)
                    for o in group
                )
            )
    return lines


def _late_suffix(repo: Repo, o: OrderRecord) -> str:
    late = leases.not_confirmed(repo, o.id, o.lease) if o.kind == "qa" else None
    return f" ({late})" if late else ""


def stack_driver_lines(d: BatchRecord, repo: Repo) -> list[str]:
    late = leases.not_confirmed(repo, "stack", d.stack_lease) if d.stack_agent else None
    return [f"stack driver {d.stack_agent}: {late}"] if late else []
