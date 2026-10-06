#!/usr/bin/env python3
"""Minimal Decisor client: typed decisions over an SGLang engine.

The prompt render and the letter readout are the model's own format
(decisor-4b, contract v3); the engine only provides /tokenize and
/generate. Everything else lives here, in the open.
"""

import json
import math
import socket
import urllib.error
import urllib.request

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SUFFIX = "\nA:"
MAX_OPTIONS = 18  # decisor-4b contract v3

HEADER = (
    "You make decisions with exactly one letter. Read the state, apply "
    "the question, and pick from the listed options.\n"
    "Semantics: a field absent from the state is unknown — it is neither "
    "true nor false. Use the insufficient-information option, when "
    "listed, only if a missing fact would change the decision; otherwise "
    "decide with the facts given.\n\n"
    "STATE (JSON):\n"
)
Q_TPL = "\nQ: {q}\nOptions: {opts}\nA:"

_TOKEN_CACHE: dict[tuple[str, int], list[list[int]]] = {}


class DecisorError(RuntimeError):
    """Clear failure: bad input, HTTP, connection or timeout."""


def render(state, question, option_texts) -> str:
    """Render the exact decisor-4b training format."""
    opts = " ".join(f"({LETTERS[i]}) {t}" for i, t in enumerate(option_texts))
    return HEADER + json.dumps(state, ensure_ascii=False) + \
        Q_TPL.format(q=question, opts=opts)


def _logsumexp(xs) -> float:
    m = max(xs)
    return m + math.log(sum(math.exp(x - m) for x in xs))


def _post(base, path, payload, timeout_s, api_key=None) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        raise DecisorError(
            f"server returned HTTP {e.code} for {path}: {body}") from None
    except socket.timeout:
        raise DecisorError(
            f"timeout after {timeout_s}s calling {path} at {base}") from None
    except urllib.error.URLError as e:
        raise DecisorError(f"cannot reach engine at {base}: {e.reason}") from None
    except ValueError:
        raise DecisorError(f"server returned a non-JSON reply for {path}") from None


def letter_ids(base, k, api_key=None, timeout_s=60.0) -> list[list[int]]:
    """Single-token ids of the letter forms per class (in-memory cache).

    Mirrors the training readout: tokenize the decision suffix, then the
    suffix plus each form ('A', ' A', '(A'); a form counts only when it
    adds exactly one token. Ids shared by two classes are rejected.
    """
    key = (base.rstrip("/"), k)
    if key in _TOKEN_CACHE:
        return _TOKEN_CACHE[key]
    pref = _post(base, "/tokenize", {"prompt": SUFFIX}, timeout_s,
                 api_key)["tokens"]
    shapes: list[list[int]] = []
    owner: dict[int, int] = {}
    for c in range(k):
        letter = LETTERS[c]
        ids: list[int] = []
        for form in (letter, " " + letter, "(" + letter):
            toks = _post(base, "/tokenize",
                         {"prompt": SUFFIX + form}, timeout_s,
                         api_key)["tokens"]
            if toks[:len(pref)] == pref and len(toks) == len(pref) + 1:
                tid = toks[-1]
                if tid in owner and owner[tid] != c:
                    raise DecisorError(
                        f"token id {tid} maps to classes "
                        f"{LETTERS[owner[tid]]} and {letter}: "
                        "ambiguous readout, refusing to decide")
                if tid not in ids:
                    ids.append(tid)
                owner[tid] = c
        if not ids:
            raise DecisorError(f"class {letter} has no single-token form")
        shapes.append(ids)
    _TOKEN_CACHE[key] = shapes
    return shapes


def decide(host, state, question, options, api_key=None, timeout_s=60.0) -> dict:
    """One typed decision: state + question + options -> distribution.

    options: list of {"id": str, "text": str}; the first option is A.
    api_key: optional; sent as Authorization: Bearer.
    """
    if not isinstance(options, list) or not 2 <= len(options) <= MAX_OPTIONS:
        raise DecisorError(f"options must be a list of 2..{MAX_OPTIONS} items")
    ids = [o["id"] for o in options]
    texts = [o["text"] for o in options]
    if any(not str(i).strip() for i in ids) or len(set(ids)) != len(ids):
        raise DecisorError("option ids must be non-empty and unique")
    if not str(question).strip():
        raise DecisorError("question must not be empty")

    shapes = letter_ids(host, len(options), api_key, timeout_s)
    prompt = render(state, question, texts)
    all_ids = [t for shape in shapes for t in shape]
    payload = {
        "text": prompt,
        "sampling_params": {"max_new_tokens": 1, "temperature": 0},
        "return_logprob": True,
        "top_logprobs_num": 0,
        "logprob_start_len": -1,
        "token_ids_logprob": all_ids,
    }
    reply = _post(host, "/generate", payload, timeout_s, api_key)
    triples = (reply.get("meta_info") or {}).get("output_token_ids_logprobs")
    if triples and isinstance(triples[0], list) and triples[0] \
            and isinstance(triples[0][0], list):
        triples = triples[0]
    if not triples:
        raise DecisorError("engine reply has no output_token_ids_logprobs")
    got = {int(t[1]): float(t[0]) for t in triples}
    missing = [t for t in all_ids if t not in got]
    if missing:
        raise DecisorError(
            f"engine omitted {len(missing)} requested token ids "
            f"(e.g. {missing[:5]})")

    # Readout: log-softmax over the letter forms, logsumexp per class,
    # renormalised across the options (training semantics).
    sel = [got[t] for t in all_ids]
    lse = _logsumexp(sel)
    probs: list[float] = []
    i = 0
    for shape in shapes:
        class_lp = _logsumexp([x - lse for x in sel[i:i + len(shape)]])
        probs.append(math.exp(class_lp))
        i += len(shape)
    total = sum(probs)
    probs = [p / max(total, 1e-9) for p in probs]
    best = max(range(len(options)), key=lambda j: (probs[j], -j))
    return {
        "decision": ids[best],
        "options": [{"id": ids[j], "prob": probs[j]}
                    for j in range(len(options))],
    }
