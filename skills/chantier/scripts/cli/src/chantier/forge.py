"""The forge, through its CLI. GitHub (`gh`) is supported; GitLab is refused with exit 4.

`CHANTIER_GH`, else `gh` in .agents/chantier.json, names the `gh` executable (tests and simulations put a
fake one there).
"""
from __future__ import annotations

import json
import os
import subprocess

from .state import ChantierError, EXIT_EXTERNAL

INFRA_HINTS = ("runner", "timed out", "timeout", "network", "econnreset", "rate limit",
               "no space left", "cancelled", "service unavailable", "502", "503")


def _check_forge(config: dict) -> None:
    if config.get("forge", "github") != "github":
        raise ChantierError(f"forge {config['forge']!r} is not supported yet; only github", EXIT_EXTERNAL)


def gh(*args: str, cwd=None, config: dict | None = None) -> str:
    _check_forge(config or {})
    exe = os.environ.get("CHANTIER_GH") or (config or {}).get("gh") or "gh"
    env = {**os.environ, "GH_PAGER": "cat", "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"}
    try:
        p = subprocess.run([exe, *args], cwd=cwd, capture_output=True, text=True, env=env,
                           timeout=120)
    except FileNotFoundError as e:
        raise ChantierError(f"{exe} not found", EXIT_EXTERNAL) from e
    except subprocess.TimeoutExpired as e:
        raise ChantierError(f"{exe} {' '.join(args)} timed out", EXIT_EXTERNAL) from e
    if p.returncode != 0:
        raise ChantierError(f"{exe} {' '.join(args[:3])}: {p.stderr.strip()[:300]}", EXIT_EXTERNAL)
    return p.stdout.strip()


def pr_create(cwd, config: dict, base: str, head: str, title: str, body_file: str) -> str:
    out = gh("pr", "create", "--base", base, "--head", head, "--title", title,
             "--body-file", body_file, cwd=cwd, config=config)
    return out.splitlines()[-1].strip()


def pr_edit(cwd, config: dict, pr: str, body_file: str | None = None, base: str | None = None):
    args = ["pr", "edit", pr]
    if body_file:
        args += ["--body-file", body_file]
    if base:
        args += ["--base", base]
    gh(*args, cwd=cwd, config=config)


def pr_checks(cwd, config: dict, pr: str) -> list[dict]:
    """Checks of a PR: name, bucket (pass, fail, pending, skipping, cancel) and link."""
    out = gh("pr", "checks", pr, "--json", "name,bucket,link", cwd=cwd, config=config)
    return json.loads(out or "[]")


def main_failures(cwd, config: dict, branch: str) -> set[str]:
    """Names of failed checks in the latest completed run on the default branch."""
    out = gh("run", "list", "--branch", branch, "--limit", "20", "--json",
             "name,conclusion,status", cwd=cwd, config=config)
    runs = json.loads(out or "[]")
    return {r["name"] for r in runs if r.get("conclusion") == "failure"}


def failed_log(cwd, config: dict, link: str) -> str:
    """Tail of a failed check's log, when the forge gives it; empty otherwise."""
    run_id = link.rstrip("/").split("/runs/")[-1].split("/")[0] if "/runs/" in link else ""
    if not run_id.isdigit():
        return ""
    try:
        return gh("run", "view", run_id, "--log-failed", cwd=cwd, config=config)[-4000:]
    except ChantierError:
        return ""


def classify(checks: list[dict], red_on_main: set[str], logs: dict[str, str]) -> str:
    failed = [c for c in checks if c.get("bucket") in {"fail", "cancel"}]
    if not failed:
        return "none"
    if all(c["name"] in red_on_main for c in failed):
        return "known-red-on-main"
    if all(c.get("bucket") == "cancel"
           or any(h in logs.get(c["name"], "").lower() for h in INFRA_HINTS) for c in failed):
        return "infra"
    return "product"
