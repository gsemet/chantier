"""The ids of batches and CRs, in one spelling. No pydantic: the CLI's start-up reads them."""

from __future__ import annotations

import re
from typing import overload


def normalize_batch(batch: str) -> str:
    """`4`, `04` and `batch-04` all name `batch-04`; anything else is left as given."""
    match = re.fullmatch(r"(?:batch-)?(\d+)", batch.strip())
    return f"batch-{int(match.group(1)):02d}" if match else batch


@overload
def normalize_cr(value: str) -> str: ...
@overload
def normalize_cr(value: None) -> None: ...
def normalize_cr(value: str | None) -> str | None:
    """`165`, `CR-165` and `cr-165` all name `CR-165`; anything else (`stack`, `-`, an `O-k`
    order, a QA folder) is left as given."""
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"(?:cr-)?(\d+)", value.strip(), re.I)
    return f"CR-{match.group(1)}" if match else value
