#!/usr/bin/env python3
"""Apply the upstream PR #35052 logprobs guards to the installed batch_result_processor.py."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SHA_TAG = "e4fb82ba6bc501f2e8f29a0fc76ce240d1d128210122619c899917433c2b6ddb"

SUBS = [
    (
        "                    v.tolist() for v in logits_output.next_token_top_logprobs_val\n",
        "                    (v.tolist() if torch.is_tensor(v) else v)\n"
        "                    for v in logits_output.next_token_top_logprobs_val\n",
        2,
    ),
    (
        "                    x.tolist() for x in logits_output.next_token_top_logprobs_idx\n",
        "                    (x.tolist() if torch.is_tensor(x) else x)\n"
        "                    for x in logits_output.next_token_top_logprobs_idx\n",
        2,
    ),
    (
        "                    v.tolist() for v in logits_output.next_token_token_ids_logprobs_val\n",
        "                    (v.tolist() if torch.is_tensor(v) else v)\n"
        "                    for v in logits_output.next_token_token_ids_logprobs_val\n",
        2,
    ),
]


def main() -> int:
    sys.dont_write_bytecode = True  # no .pyc written (clean delta vs base)
    import sglang

    root = Path(sglang.__file__).parent
    p = root / "srt" / "managers" / "scheduler_components" / "batch_result_processor.py"
    b = p.read_bytes()
    sha_before = hashlib.sha256(b).hexdigest()
    print(f"target: {p}")
    print(f"sha256 BEFORE: {sha_before}")
    if sha_before != EXPECTED_SHA_TAG:
        print(
            "FAIL: installed batch_result_processor.py is NOT byte-identical "
            f"to the v0.5.20 tag (want {EXPECTED_SHA_TAG}) — STOP: patch not applied.",
            file=sys.stderr,
        )
        return 2

    text = b.decode("utf-8")
    applied = []
    for old, new, want in SUBS:
        got = text.count(old)
        if got != want:
            print(f"FAIL: pattern found {got} time(s) (expected {want}): {old.strip()!r}", file=sys.stderr)
            return 3
        text = text.replace(old, new)
        applied.append({"site": old.strip(), "count": got})
    n_guard = text.count("torch.is_tensor")
    if n_guard != 7:
        print(f"FAIL: torch.is_tensor count final {n_guard} != 7", file=sys.stderr)
        return 4
    patched = text.encode("utf-8")
    sha_after = hashlib.sha256(patched).hexdigest()

    ref = None
    if len(sys.argv) > 1:
        ref_path = Path(sys.argv[1])
        ref = ref_path.read_bytes()
        if ref != patched:
            print("FAIL: in-image patched file diverges byte-a-byte from the reference patched file (patches/brp-v0.5.20-p35052.py).", file=sys.stderr)
            return 5
        print("byte cross-check against the reference patched file: OK")

    p.write_bytes(patched)
    print(f"sha256 AFTER: {sha_after}")

    out_dir = Path("/opt/p35052-patch")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "target_file": str(p),
        "sha256_before": sha_before,
        "sha256_after": sha_after,
        "upstream_pr": 35052,
        "sites_patched": 6,
        "subs": applied,
        "reference_patched_sha256": hashlib.sha256(ref).hexdigest() if ref is not None else None,
        "applied_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"manifest: {out_dir/'manifest.json'}")
    print("PATCH OK (6 torch.is_tensor guard sites)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
