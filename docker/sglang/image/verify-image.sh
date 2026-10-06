#!/usr/bin/env bash
# Content-based verification of the loader-fix image.
#
# Usage: ./verify-image.sh <image-tag>
# Container CLI: defaults to `docker`; override with CONTAINER_CLI=podman.
# CPU only; verification is by CONTENT, not by image Id.
set -euo pipefail

TAG="${1:?usage: ./verify-image.sh <image-tag>}"
BASE="docker.io/lmsysorg/sglang@sha256:b27fce60bc5494c118c4910702812bcfa8cee67abcdd1ff8b0902f21647552f4"
CONTAINER_CLI="${CONTAINER_CLI:-docker}"

LOADER_SHA="f4af2297b1c65a48ab331792f99a72169b5b9c32d5b6c6444b5814502daac830"
BRP_SHA="f225919698d1926543974864ccfb31c5b809b0fab7f82717a09d8b576470919b"
GUARD_COUNT="7"

fail=0
pass() { echo "PASS  $*"; }
crash() { echo "FAIL  $*"; fail=1; }

# (a)(b)(c) — in-image content checks in a single CPU-only run.
content_rc=0
content=$("$CONTAINER_CLI" run --rm --entrypoint /bin/bash "$TAG" -c '
  set -euo pipefail
  ROOT=$(python3 -B -c "import sglang, os; print(os.path.dirname(sglang.__file__))")
  sha256sum "$ROOT/srt/models/qwen3_5_text.py" "$ROOT/srt/managers/scheduler_components/batch_result_processor.py" | cut -d" " -f1
  grep -c "torch\.is_tensor" "$ROOT/srt/managers/scheduler_components/batch_result_processor.py" || true
') || content_rc=$?
if [ "$content_rc" -ne 0 ]; then
  crash "(a/b/c) could not read image content ($CONTAINER_CLI run exit $content_rc)"
else
  mapfile -t lines <<< "$content"
  if [ "${lines[0]:-}" = "$LOADER_SHA" ]; then
    pass "(a) qwen3_5_text.py sha256 matches the loader fix"
  else
    crash "(a) qwen3_5_text.py sha256 '${lines[0]:-<empty>}' != the loader fix ($LOADER_SHA)"
  fi
  if [ "${lines[1]:-}" = "$BRP_SHA" ]; then
    pass "(b) batch_result_processor.py sha256 matches PR #35052 applied content"
  else
    crash "(b) batch_result_processor.py sha256 '${lines[1]:-<empty>}' != expected ($BRP_SHA)"
  fi
  if [ "${lines[2]:-}" = "$GUARD_COUNT" ]; then
    pass "(c) torch.is_tensor guard count == 7"
  else
    crash "(c) torch.is_tensor guard count '${lines[2]:-<empty>}' != 7"
  fi
fi

# (d) — Env/Entrypoint/Cmd/WorkingDir identical to the pinned base image.
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
inspect_fmt='Env={{json .Config.Env}}
Entrypoint={{json .Config.Entrypoint}}
Cmd={{json .Config.Cmd}}
WorkingDir={{json .Config.WorkingDir}}'
if "$CONTAINER_CLI" image inspect --format "$inspect_fmt" "$TAG" >"$tmpdir/new.txt" 2>"$tmpdir/new.err"; then
  if "$CONTAINER_CLI" image inspect --format "$inspect_fmt" "$BASE" >"$tmpdir/base.txt" 2>"$tmpdir/base.err"; then
    if diff -u "$tmpdir/base.txt" "$tmpdir/new.txt" >"$tmpdir/config.diff"; then
      pass "(d) Env/Entrypoint/Cmd/WorkingDir identical to base"
    else
      crash "(d) Config differs from base (see diff below)"
      cat "$tmpdir/config.diff"
    fi
  else
    crash "(d) base image $BASE not available locally ($CONTAINER_CLI pull it first)"
  fi
else
  crash "(d) could not inspect built image: $(cat "$tmpdir/new.err")"
fi

# (e) — provenance manifests present.
if "$CONTAINER_CLI" run --rm --entrypoint /bin/bash "$TAG" -c \
  'test -f /opt/loader-patch/manifest.json && test -f /opt/p35052-patch/manifest.json' 2>/dev/null; then
  pass "(e) /opt/loader-patch/manifest.json and /opt/p35052-patch/manifest.json present"
else
  crash "(e) provenance manifests missing under /opt"
fi

# (f) — PR #35852 unit test passes in-image (CPU only).
if test_out=$("$CONTAINER_CLI" run --rm --entrypoint /bin/bash "$TAG" -c \
  'cd /opt/p35052-patch && python3 -B -m unittest test_batch_result_processor_logprobs -v' 2>&1); then
  pass "(f) PR #35852 unit test passes in-image"
  echo "$test_out" | tail -4
else
  crash "(f) PR #35852 unit test FAILED in-image"
  echo "$test_out" | tail -20
  fail=1
fi

echo "--------------------------------------------------------------"
if [ "$fail" -eq 0 ]; then
  echo "VERIFY: ALL CHECKS PASSED  ($TAG)"
else
  echo "VERIFY: FAILURES PRESENT   ($TAG)"
fi
exit "$fail"
