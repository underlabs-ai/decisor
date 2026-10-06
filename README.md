# decisor

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#installation)
[![Model](https://img.shields.io/badge/%F0%9F%A4%97-decisor--4b-yellow.svg)](https://huggingface.co/underlabs/decisor-4b)

A minimal Python SDK and patched SGLang inference server for
[decisor-4b](https://huggingface.co/underlabs/decisor-4b), a typed-decision
model.

The model was trained for decision tasks in English and Brazilian
Portuguese, with additional emphasis on Brazilian legal and tax contexts.

You supply a state, a question, and a set of options. You get back
the chosen option and a probability distribution over the options,
computed from next-token scores produced by a single prefill pass,
without generating a free-form answer. The repo includes a CLI demo
and examples in English and Brazilian Portuguese.

Developed by [Under Labs](https://underlabs.ai).

> [!WARNING]
> **Technical preview (v0.1.0).** For local experimentation and integration.
> Not a production-ready deployment. Legal and tax outputs require
> professional review against current authoritative sources.

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Request and response format](#request-and-response-format)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Repository layout](#repository-layout)
- [License](#license)
- [Citation](#citation)

## How it works

```text
state + question + options ──► prefill pass ──► logits at the final position ──► distribution over option ids
```

The SDK renders your request into the model's typed-decision prompt, resolves
the option-letter token ids through the engine, and reads the scores from the
logits at the end of the prefill pass. The current engine request emits one
token, but the SDK computes the decision from the scores produced during
prefill, not from generated answer text. Successful calls return a supplied
option id rather than a free-form answer.

## Requirements

- NVIDIA GPU with container GPU support (NVIDIA Container Toolkit)
- Docker (29.8 was used on the tested RTX 5090)
- Python 3.10+
- [just](https://github.com/casey/just)
- About 7.1 GB for the model weights, plus space for the engine image,
  cache metadata, and temporary download files

**Tested hardware:** NVIDIA RTX 5090 (32 GB) and RTX PRO 6000 Blackwell
Server Edition (96 GB). Smaller GPUs have not been tested; a model file that
fits in a card's memory does not show that the card is compatible.

## Installation

### 1. Configure

```bash
cp .env.example .env
```

Generate an API key and set `SGLANG_API_KEY` in `.env`:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Keep the key private. Never commit `.env`. Users with access to Docker
on this machine can inspect the key through the container command line.

### 2. Start the engine

On first startup, the engine downloads the
[underlabs/decisor-4b](https://huggingface.co/underlabs/decisor-4b) weights
(about 7.1 GB) and caches them for later runs. This release distributes
the FP8 model for SGLang only.

```bash
just sglang-pull     # download the engine image
just sglang-up       # start the engine
just sglang-status   # check readiness
just sglang-smoke    # check inference and logprobs
```

Repeat `just sglang-status` while the first download and model load finish.

### 3. (Optional) Install the Python SDK

Only needed to import the SDK from another Python project; the demo and the
example commands run from this repository without it.

```bash
pip install ./sdks/python
```

## Usage

### Interactive demo

```bash
just demo
```

Example output (12 days since delivery, item not used — within the policy):

```text
Decision: approved

Option        Probability
approved           1.0000
rejected           0.0000
insufficient       0.0000
```

Option probabilities describe the model's distribution over the supplied
options. They are not calibrated estimates of correctness.

### From a request file

```bash
just decide fixtures/refund.en.json
just decide fixtures/refund.pt-BR.json
```

### Python

The `just` launcher reads `.env`; standalone Python does not. Export the same
key in your shell first:

```bash
export SGLANG_API_KEY=...
```

```python
import os
from decisor import decide

result = decide(
    "http://127.0.0.1:8768",
    api_key=os.environ["SGLANG_API_KEY"],
    state={
        "policy": "Refunds are allowed for unused items within 30 days of delivery.",
        "request": {"days_since_delivery": 12, "item_unused": True},
    },
    question="Is the refund allowed under this policy?",
    options=[
        {"id": "approved", "text": "Refund allowed"},
        {"id": "rejected", "text": "Refund not allowed"},
        {"id": "insufficient", "text": "Not enough information"},
    ],
)
print(result["decision"])
```

Example response (probabilities rounded for display):

```json
{
  "decision": "approved",
  "options": [
    {"id": "approved", "prob": 1.0},
    {"id": "rejected", "prob": 0.0},
    {"id": "insufficient", "prob": 0.0}
  ]
}
```

### Commands

| Command | Description |
|---|---|
| `just demo` | Try an interactive decision |
| `just decide <file>` | Decide on a request file |
| `just sglang-pull` | Download the engine image |
| `just sglang-up` | Start the engine |
| `just sglang-status` | Check status and health |
| `just sglang-logs` | Follow logs |
| `just sglang-down` | Stop the engine |
| `just sglang-smoke` | Check inference and logprobs |
| `just sglang-build` | Advanced: build the engine image locally |

Advanced: set `SGLANG_MODEL_PATH` in `.env` to use a local checkpoint
instead of the Hugging Face repository. A local build produces
`decisor-sglang:0.5.20`; set `SGLANG_IMAGE` to that tag to use it.

## Request and response format

Request files accept the object below directly or inside a `request` wrapper.
`just decide` ignores the fixture's `expected` field.

```json
{
  "state": {
    "policy": "Refunds are allowed for unused items within 30 days of delivery.",
    "request": {"days_since_delivery": 12, "item_unused": true}
  },
  "question": "Is the refund allowed under this policy?",
  "options": [
    {"id": "approved", "text": "Refund allowed"},
    {"id": "rejected", "text": "Refund not allowed"},
    {"id": "insufficient", "text": "Not enough information"}
  ]
}
```

Example response (probabilities rounded for display):

```json
{
  "decision": "approved",
  "options": [
    {"id": "approved", "prob": 1.0},
    {"id": "rejected", "prob": 0.0},
    {"id": "insufficient", "prob": 0.0}
  ]
}
```

**Limits:** the SDK accepts 2 to 18 options per request and rejects more;
ties resolve to the first option. These are SDK limits and behaviour, not a
qualification of every cardinality on the distributed model. Failures raise
a clear error (connection, HTTP status, timeout).

## Configuration

| Variable | Default | Description |
|---|---|---|
| `SGLANG_API_KEY` | none (required) | API key for the engine |
| `SGLANG_IMAGE` | `decisor-sglang:0.5.20` (local build) | Engine image |
| `SGLANG_MODEL_REPO` | `underlabs/decisor-4b` | Hugging Face repository used when no local path is set |
| `SGLANG_MODEL_PATH` | empty | Local checkpoint directory (overrides the repository) |
| `SGLANG_GPU_DEVICE` | `0` | GPU device id |
| `SGLANG_PORT` | `8768` | Host port (bound to 127.0.0.1) |
| `SGLANG_MEM_FRACTION` | `0.80` | VRAM fraction for weights + KV cache |
| `SGLANG_EXTRA_ARGS` | prefill graph off, radix cache off | Extra engine flags |

This is a local example, not a production deployment. Keep the port private
and use HTTPS when you access it over a network.

## Limitations

- Technical preview; not production-ready.
- Probabilities are not calibrated confidence.
- Legal and tax outputs require professional review.
- Not tested on GPUs smaller than those listed.
- Performance varies by language, domain and task.

## Troubleshooting

| Symptom | Check |
|---|---|
| `401` unauthorized | Is `SGLANG_API_KEY` set? The launcher reads `.env`; standalone Python needs it exported. |
| Engine never becomes healthy | `just sglang-logs` — the first startup downloads about 7.1 GB. |
| Model fails to load | Check the engine logs and available VRAM. A static memory fraction that is too low can prevent loading. |
| Out of memory during inference | Check other GPU processes; reducing the static memory fraction, context length, or concurrency may help. |
| GPU not visible in the container | Check the NVIDIA Container Toolkit (run `nvidia-smi` inside the container). |

## Repository layout

```text
sdks/python/    Python SDK (decisor.py), example CLI, demo and decide
scripts/        Launcher scripts (start, smoke)
docker/sglang/  Compose files and the engine image build kit
fixtures/       Example requests (English and Brazilian Portuguese)
justfile        Command recipes
```

## License

- **Code (this repository):** Apache-2.0. See [LICENSE](LICENSE).
- **Model weights:** Apache-2.0, license and notices included in the
  [decisor-4b](https://huggingface.co/underlabs/decisor-4b) package.
- Built on [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), whose terms
  apply.
- The engine image includes a fused-checkpoint loader fix and the logprobs
  guard from SGLang PR
  [#35052](https://github.com/sgl-project/sglang/pull/35052), with an
  in-build regression test from PR
  [#35852](https://github.com/sgl-project/sglang/pull/35852). Upstream
  license files are preserved.

## Citation

```bibtex
@software{decisor2026,
  title  = {decisor-4b: typed one-pass decisions},
  author = {{Under Labs}},
  year   = {2026},
  url    = {https://huggingface.co/underlabs/decisor-4b}
}
```
