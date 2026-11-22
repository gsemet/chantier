"""What an op's handler returns: an HTTP status and the route's JSON answer as `data`."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any


@dataclass
class Result:
    status: int
    data: dict[str, Any] | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return HTTPStatus.OK <= self.status < HTTPStatus.MULTIPLE_CHOICES


def fail(status: int, error: str) -> Result:
    return Result(status, None, error)
