"""The error every command raises, and the exit codes it carries."""

from __future__ import annotations

EXIT_USAGE, EXIT_PRECONDITION, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_BUDGET = 1, 2, 3, 4, 5


class ChantierError(Exception):
    """An error with the exit code the CLI must return."""

    def __init__(self, message: str, code: int = EXIT_PRECONDITION):
        super().__init__(message)
        self.code = code
