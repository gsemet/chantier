"""The base of the published journal models (`schemas.py`, `schemas_sync.py`): the payload base
class and the commit SHA type they share, kept here so both can import them with no cycle."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

SHA = r"^([0-9a-f]{40}|[0-9a-f]{64})$"

Sha = Annotated[str, StringConstraints(pattern=SHA)]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
