# `done` on an unknown id: an error, not a traceback

## Change

- `tasks done <id>` with an id that no task has prints `error: no task <id>` and returns exit
  code 1. No traceback. The tasks file is not modified.

## Done when

- A test covers an unknown id: the message, the exit code, and the file left unchanged.
- The fast and long gates pass.
