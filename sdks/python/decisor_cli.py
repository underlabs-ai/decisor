#!/usr/bin/env python3
"""Run fixture files against a Decisor engine (example CLI for the SDK).

Fixtures may carry state/question/options directly or inside a
"request" wrapper. "expected.decision", when present, is a
human-declared label compared for information only: divergences do not
change the exit code; execution errors exit non-zero.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from decisor import DecisorError, decide


def _fixtures(path: Path) -> list[Path]:
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not files or not all(f.is_file() for f in files):
        raise SystemExit(f"error: no fixture file or directory: {path}")
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="decisor-cli",
        description="Run fixture files (request + expected) against a "
                    "Decisor engine. Only the request is sent; expected "
                    "is a human-declared label, never part of the payload.")
    ap.add_argument("path", help="fixture file or directory of .json fixtures")
    ap.add_argument("--host",
                    default=os.environ.get("DECISOR_HOST") or
                    ("http://127.0.0.1:" + os.environ.get("SGLANG_PORT",
                                                          "8768")))
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)
    api_key = os.environ.get("SGLANG_API_KEY") or None

    files = _fixtures(Path(args.path))
    matched = divergent = 0
    for f in files:
        try:
            fixture = json.loads(f.read_text(encoding="utf-8"))
            req = fixture.get("request", fixture)
        except (OSError, ValueError) as e:
            print(f"{f}: invalid fixture: {e}", file=sys.stderr)
            return 1
        if not isinstance(req, dict) or \
                not all(k in req for k in ("state", "question", "options")):
            print(f"{f}: invalid fixture: state, question and options "
                  "are required", file=sys.stderr)
            return 1
        try:
            result = decide(args.host, req["state"], req["question"],
                            req["options"], api_key=api_key,
                            timeout_s=args.timeout)
        except DecisorError as e:
            print(f"{f}: {e}", file=sys.stderr)
            return 1
        probs = " ".join(f"{o['id']}={o['prob']:.4f}"
                         for o in result["options"])
        print(f"{f}")
        print(f"  decision: {result['decision']}")
        print(f"  options:  {probs}")
        expected = (fixture.get("expected") or {}).get("decision")
        if expected is not None:
            ok = expected == result["decision"]
            matched += ok
            divergent += not ok
            print(f"  expected: {expected} — {'match' if ok else 'DIVERGENT'}")
    print("---")
    print(f"fixtures: {len(files)} · matched: {matched} · divergent: {divergent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
