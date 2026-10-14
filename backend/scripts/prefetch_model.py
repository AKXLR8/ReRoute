"""Vercel build hook — bake the ONNX embedding model into .hf/ so it ships in
the function bundle (runtime FS is read-only; never download at request time).

Wired via [tool.vercel.scripts] in pyproject.toml; runs after deps install.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[1] / ".hf"))

from huggingface_hub import snapshot_download  # noqa: E402

from reroute.config import get_settings  # noqa: E402

name = get_settings().embedding_model
print(f"prefetch: downloading {name}", file=sys.stderr)
snapshot_download(name, allow_patterns=["tokenizer.json", "onnx/model_quantized.onnx"])
print("prefetch: bundled into .hf/", file=sys.stderr)
