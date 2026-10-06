#!/usr/bin/env python3
"""Decide on a request file: state, question and options (a "request"
wrapper is accepted; "expected" is ignored)."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from decisor import DecisorError, decide


def _show(result: dict, elapsed_ms: float) -> None:
    print(f"\nDecision: {result['decision']}\n")
    width = max(len("Option"), *(len(o["id"]) for o in result["options"])) + 2
    print(f"{'Option':<{width}}Probability")
    for o in result["options"]:
        print(f"{o['id']:<{width}}{o['prob']:>11.4f}")
    print(f"\nElapsed: {elapsed_ms:.1f} ms")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="decisor-decide",
        description="Decide on a request JSON file: state, question and "
                    "options. A request wrapper is accepted; expected is "
                    "ignored.")
    ap.add_argument("file", help="request JSON file")
    ap.add_argument("--host",
                    default=os.environ.get("DECISOR_HOST") or
                    ("http://127.0.0.1:" + os.environ.get("SGLANG_PORT",
                                                          "8768")))
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)

    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"error: cannot read {args.file}: {e}", file=sys.stderr)
        return 1
    req = data.get("request", data) if isinstance(data, dict) else None
    if not isinstance(req, dict) or \
            not all(k in req for k in ("state", "question", "options")):
        print(f"error: {args.file} must contain state, question and options",
              file=sys.stderr)
        return 1

    print("Request:")
    print(json.dumps({"state": req["state"], "question": req["question"],
                      "options": req["options"]},
                     indent=2, ensure_ascii=False))

    api_key = os.environ.get("SGLANG_API_KEY") or None
    try:
        t0 = time.perf_counter()
        result = decide(args.host, req["state"], req["question"],
                        req["options"], api_key=api_key,
                        timeout_s=args.timeout)
    except DecisorError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _show(result, (time.perf_counter() - t0) * 1000.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
