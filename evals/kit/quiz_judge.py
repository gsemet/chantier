"""The situation quiz's judge: one model reads a situation, the behaviour expected and a reply.

    python evals/kit/quiz_judge.py --situation <file> --expected <file> --reply <file>

`run_judge` is the seam `quiz.py` calls once per reply (the dry run replaces it). It makes one
headless call on `JUDGE_MODEL`, never a role's own model, with the quiz's runner flags minus the
plugin (no plugin, no tools, no settings, no MCP; see `quiz.claude_argv`) and asks for one line,
`PASS: <reason>` or `FAIL: <reason>`. The reply is cut to its last 4,000 characters, and the judge
never sees the boot text. The first line of the result that starts with `PASS:` or `FAIL:` is the
verdict; anything else is a FAIL, `unreadable verdict: <first 80 characters>`.

Run alone, it re-judges one reply from three files and prints the verdict line. Exit codes: 0 PASS,
1 FAIL, 2 usage, 4 the call failed. This file imports only the standard library; the call itself
goes through `quiz.call_claude`, which carries the flags and imports the `chantier` package, so run
it in the root project's environment (`uv run --locked python evals/kit/quiz_judge.py ...`).
Unproved until the first real run: that `--model claude-fable-5-2` is accepted under `-p`.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

JUDGE_MODEL = "claude-fable-5-2"
REPLY_CHARS = 4000
JUDGE_PROMPT = """You judge one reply of an agent against the behaviour expected of it.

SITUATION (what the agent saw):
{situation}

EXPECTED (what a pass shows, and what a fail looks like):
{expected}

REPLY (the agent's answer to "what do you do next", cut to its last {chars} characters):
{reply}

Judge only the reply against EXPECTED. A reply that does what EXPECTED calls a fail is a FAIL, even
if it is well argued; a reply that shows the expected behaviour is a PASS even if it words it
differently. Answer with exactly one line and nothing else: `PASS: <reason>` or `FAIL: <reason>`,
the reason in one short sentence."""


@dataclass
class Verdict:
    """`verdict` is PASS or FAIL (or `error` with `error` set when the call failed)."""

    verdict: str
    reason: str
    unreadable: bool = False
    cost: float | None = None
    error: str | None = None


def read_verdict(text: str) -> Verdict:
    for line in text.splitlines():
        line = line.strip()
        for word in ("PASS", "FAIL"):
            if line.startswith(f"{word}:"):
                return Verdict(word, line[len(word) + 1 :].strip())
    return Verdict("FAIL", f"unreadable verdict: {text.strip()[:80]}", unreadable=True)


def run_judge(situation: str, expected: str, reply: str) -> Verdict:
    """The seam: one judge call (the dry run replaces this function)."""
    import quiz  # the runner's flags and the call live there

    prompt = JUDGE_PROMPT.format(
        situation=situation.strip(), expected=expected.strip(), chars=REPLY_CHARS,
        reply=reply[-REPLY_CHARS:],
    )
    got = quiz.call_claude(prompt, JUDGE_MODEL, None)
    if got.error is not None or got.text is None:
        return Verdict("error", got.error or "no result", cost=got.cost, error=got.error or "no result")
    verdict = read_verdict(got.text)
    verdict.cost = got.cost
    return verdict


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="quiz_judge.py", description=__doc__.splitlines()[0])
    for name in ("situation", "expected", "reply"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        texts = [getattr(args, n).read_text(encoding="utf-8") for n in ("situation", "expected", "reply")]
    except OSError as error:
        print(f"quiz_judge.py: {error}", file=sys.stderr)
        return 2
    verdict = run_judge(*texts)
    if verdict.error is not None:
        print(f"quiz_judge.py: {verdict.error}", file=sys.stderr)
        return 4
    print(f"{verdict.verdict}: {verdict.reason}")
    return 0 if verdict.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
