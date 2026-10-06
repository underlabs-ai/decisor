#!/usr/bin/env python3
"""Interactive demo: one refund decision through the real SDK."""

import json
import os
import sys
import time

from decisor import DecisorError, decide

POLICY = "Refunds are allowed for unused items within 30 days of delivery."
QUESTION = "Is the refund allowed under this policy?"
OPTIONS = [
    {"id": "approved", "text": "covered/approved under the policy"},
    {"id": "rejected", "text": "not covered — the policy rejects it"},
    {"id": "insufficient", "text": "not enough information to decide"},
]


def _host() -> str:
    return os.environ.get("DECISOR_HOST") or (
        "http://127.0.0.1:" + os.environ.get("SGLANG_PORT", "8768"))


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip() or str(default)
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _ask_bool(prompt: str, default: bool) -> bool:
    raw = input(f"{prompt} (y/n) [{'y' if default else 'n'}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _show(result: dict, elapsed_ms: float) -> None:
    print(f"\nDecision: {result['decision']}\n")
    width = max(len("Option"), *(len(o["id"]) for o in result["options"])) + 2
    print(f"{'Option':<{width}}Probability")
    for o in result["options"]:
        print(f"{o['id']:<{width}}{o['prob']:>11.4f}")
    print(f"\nElapsed: {elapsed_ms:.1f} ms")


def main() -> int:
    api_key = os.environ.get("SGLANG_API_KEY") or None
    while True:
        print(f"Policy: {POLICY}\n")
        try:
            days = _ask_int("Days since delivery", 12)
            used = _ask_bool("Has the item been used", False)
        except EOFError:
            return 0
        request = {
            "state": {
                "policy": POLICY,
                "request": {"days_since_delivery": days,
                            "item_unused": not used},
            },
            "question": QUESTION,
            "options": OPTIONS,
        }
        print("\nRequest:")
        print(json.dumps(request, indent=2, ensure_ascii=False))
        try:
            t0 = time.perf_counter()
            result = decide(_host(), request["state"], request["question"],
                            request["options"], api_key=api_key)
            _show(result, (time.perf_counter() - t0) * 1000.0)
        except DecisorError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        try:
            again = input("\nPress Enter to quit, or type anything to run again: ")
        except EOFError:
            return 0
        if not again:
            return 0


if __name__ == "__main__":
    sys.exit(main())
