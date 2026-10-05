"""Run the agent eval: ``uv run --project core python evals/run_eval.py``.

Each case runs on a fresh in-process core (no socket) and checks the route
taken (fast path vs LLM), the tools called in order, any tool error codes and
a substring of the spoken reply. Exits non-zero if any case fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from donna_core.app import build_core
from donna_core.bus import Event

CASES = Path(__file__).with_name("cases.json")


async def run_case(case: dict[str, Any]) -> tuple[bool, list[str], float]:
    core = build_core()
    events: list[Event] = []

    async def record(event: Event) -> None:
        events.append(event)

    core.bus.subscribe(record)
    started = time.perf_counter()
    await core.submit(case["input"])
    await core.turns.wait()
    elapsed_ms = (time.perf_counter() - started) * 1000

    def payloads(type_: str) -> list[Any]:
        return [e.payload for e in events if e.type == type_]

    route = next((p.route for p in payloads("turn.completed")), None)
    tools = [p.tool for p in payloads("tool.request")]
    errors = [p.code for p in payloads("tool.error")]
    reply = " ".join(p.text for p in payloads("assistant.text"))

    problems = []
    if route != case["route"]:
        problems.append(f"route {route!r} != {case['route']!r}")
    if tools != case["tools"]:
        problems.append(f"tools {tools} != {case['tools']}")
    if errors != case.get("tool_errors", []):
        problems.append(f"tool errors {errors} != {case.get('tool_errors', [])}")
    if case["reply_contains"].casefold() not in reply.casefold():
        problems.append(f"reply {reply!r} lacks {case['reply_contains']!r}")
    return not problems, problems, elapsed_ms


async def main(path: Path) -> int:
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    failures = 0
    print(f"{'case':38} {'result':6} {'ms':>6}")
    print("-" * 52)
    for case in cases:
        ok, problems, ms = await run_case(case)
        failures += not ok
        print(f"{case['id']:38} {'PASS' if ok else 'FAIL':6} {ms:6.1f}")
        for problem in problems:
            print(f"    - {problem}")
    print("-" * 52)
    print(f"{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=CASES)
    sys.exit(asyncio.run(main(parser.parse_args().cases)))
