#!/usr/bin/env python3
"""Smoke-check the running engine: /health then one logprobs request."""

import json
import os
import sys
import urllib.request


def main() -> int:
    base = "http://127.0.0.1:" + os.environ.get("SGLANG_PORT", "8768")
    api_key = os.environ.get("SGLANG_API_KEY") or None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    try:
        urllib.request.urlopen(base + "/health", timeout=5)
    except Exception:
        print("engine not healthy — run: just sglang-up", file=sys.stderr)
        return 1
    payload = {
        "text": "Hello decisor",
        "sampling_params": {"max_new_tokens": 1, "temperature": 0},
        "return_logprob": True,
        "top_logprobs_num": 0,
        "logprob_start_len": -1,
        "token_ids_logprob": [1, 2, 3],
    }
    req = urllib.request.Request(
        base + "/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            lp = json.load(r)["meta_info"]["output_token_ids_logprobs"]
        assert lp and lp[0]
    except Exception as e:
        print("smoke: failed — " + (str(e) or "no logprobs in the reply"), file=sys.stderr)
        return 1
    print("smoke: ok")
    for logprob, token_id, _text in lp[0]:
        print("  token " + str(token_id) + ": logprob " + str(logprob))
    return 0


if __name__ == "__main__":
    sys.exit(main())
