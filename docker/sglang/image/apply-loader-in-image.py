#!/usr/bin/env python3
"""Replace the installed qwen3_5_text.py with the fused-checkpoint loader fix."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SHA_TAG = "bf7b3c60be87ebb679396baa09808efb72921ef215468982b9df8dbbfc62efda"
EXPECTED_SHA_PATCHED = "f4af2297b1c65a48ab331792f99a72169b5b9c32d5b6c6444b5814502daac830"


def main() -> int:
    sys.dont_write_bytecode = True  # no .pyc written (clean delta vs base)
    if len(sys.argv) < 2:
        print("usage: apply-loader-in-image.py <qwen3_5_text.py.patched>", file=sys.stderr)
        return 1
    import sglang

    root = Path(sglang.__file__).parent
    p = root / "srt" / "models" / "qwen3_5_text.py"
    b = p.read_bytes()
    sha_before = hashlib.sha256(b).hexdigest()
    print(f"target: {p}")
    print(f"sha256 BEFORE: {sha_before}")
    if sha_before != EXPECTED_SHA_TAG:
        print(
            "FAIL: installed qwen3_5_text.py is NOT byte-identical to the "
            f"v0.5.20 tag (want {EXPECTED_SHA_TAG}) — STOP: patch not applied.",
            file=sys.stderr,
        )
        return 2

    patched = Path(sys.argv[1]).read_bytes()
    sha_after = hashlib.sha256(patched).hexdigest()
    if sha_after != EXPECTED_SHA_PATCHED:
        print(
            "FAIL: the patched file passed as argument diverges from the "
            f"pinned loader fix (want {EXPECTED_SHA_PATCHED}) — STOP: nothing changed.",
            file=sys.stderr,
        )
        return 3

    p.write_bytes(patched)
    print(f"sha256 AFTER: {sha_after}")

    out_dir = Path("/opt/loader-patch")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "target_file": str(p),
        "sha256_before": sha_before,
        "sha256_after": sha_after,
        "patch_source": "patches/qwen3_5_text.py.patched",
        "applied_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"manifest: {out_dir/'manifest.json'}")
    print("LOADER PATCH OK (qwen3_5_text.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
