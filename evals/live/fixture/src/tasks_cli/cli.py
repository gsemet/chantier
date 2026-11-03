"""`tasks`: a small to-do list on the command line."""
from __future__ import annotations

import argparse
import sys

from . import store


def cmd_add(args) -> int:
    tasks = store.load()
    task = {"id": store.next_id(tasks), "title": args.title, "done": False}
    tasks.append(task)
    store.save(tasks)
    print(f"added {task['id']}: {task['title']}")
    return 0


def cmd_list(args) -> int:
    for task in store.load():
        mark = "x" if task["done"] else " "
        print(f"[{mark}] {task['id']}: {task['title']}")
    return 0


def cmd_done(args) -> int:
    tasks = store.load()
    task = {t["id"]: t for t in tasks}[args.id]
    task["done"] = True
    store.save(tasks)
    print(f"done {task['id']}: {task['title']}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tasks", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("add", help="add a task")
    s.add_argument("title")
    s.set_defaults(fn=cmd_add)
    s = sub.add_parser("list", help="list the tasks")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("done", help="mark a task done")
    s.add_argument("id", type=int)
    s.set_defaults(fn=cmd_done)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
