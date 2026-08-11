#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMFY_ROOT="${COMFY_ROOT:-/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI}"
NODE_ROOT="$COMFY_ROOT/custom_nodes/comfyui-minimax-h3-context-ir-agent"
COMFY_PYTHON="$COMFY_ROOT/.venv/bin/python"
UV_BIN="${UV_BIN:-/Users/aoo/.local/bin/uv}"
REPOSITORY="https://github.com/JerryZRic/comfyui-minimax-h3-context-ir-agent.git"
COMMIT="771cb3cb01af9543b4f424518bb19b7fa0cf31d8"
LICENSE_SHA="e9da65c5e066e8b1f928c3db22ba71397bf7153ed1daf1c3c838b0a6531e3f87"
UPSTREAM_REQUIREMENTS_SHA="4194f9139f715cd433a0de6e37358bf10992372d0ff87eab45895e11879b842f"
LOCK_SHA="f3632aac1b0c9f42d78103244ff20da705cf4265e6a638b28539da49aff9bb34"
MODEL_BLOB="/Users/aoo/.ollama/models/blobs/sha256-4c7fee11ee9e3b139575eedb4cd68521729ece7fc0a356150a6672e773c607ea"
MODEL_SHA="4c7fee11ee9e3b139575eedb4cd68521729ece7fc0a356150a6672e773c607ea"
LOCKFILE="$PROJECT_ROOT/deploy/comfyui/h3-context-ir-requirements.lock"
LOCAL_PATCH="$PROJECT_ROOT/deploy/comfyui/h3-context-ir-local-instruct.patch"
LOCAL_PATCH_SHA="499703d22b4d5598ca543e8634cd6f08472cc45839899c33662eecec48d5de55"
MODE="${1:-install}"
[[ "$MODE" == "install" || "$MODE" == "--verify" ]] || { echo "usage: $0 [--verify]" >&2; exit 2; }

check_sha() {
  local expected="$1" file="$2" actual
  actual="$(shasum -a 256 "$file" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || { echo "SHA-256 mismatch: $file" >&2; exit 1; }
}

[[ -x "$COMFY_PYTHON" ]] || { echo "ComfyUI Python missing: $COMFY_PYTHON" >&2; exit 1; }
[[ -x "$UV_BIN" ]] || { echo "uv missing: $UV_BIN" >&2; exit 1; }

if [[ ! -d "$NODE_ROOT/.git" && "$MODE" == "install" ]]; then
  git clone --filter=blob:none "$REPOSITORY" "$NODE_ROOT"
fi
[[ -d "$NODE_ROOT/.git" ]] || { echo "Node checkout missing: $NODE_ROOT" >&2; exit 1; }
NODE_STATUS="$(git -C "$NODE_ROOT" status --porcelain)"
if [[ -n "$NODE_STATUS" ]]; then
  [[ "$NODE_STATUS" == " M nodes.py" ]] || { echo "Unexpected node worktree changes" >&2; exit 1; }
  NODE_DIFF_SHA="$(git -C "$NODE_ROOT" diff -- nodes.py | shasum -a 256 | awk '{print $1}')"
  [[ "$NODE_DIFF_SHA" == "$LOCAL_PATCH_SHA" ]] || { echo "Local compatibility patch mismatch" >&2; exit 1; }
elif [[ "$MODE" == "install" ]]; then
  git -C "$NODE_ROOT" fetch --quiet origin "$COMMIT"
  git -C "$NODE_ROOT" checkout --quiet --detach "$COMMIT"
  check_sha "$LOCAL_PATCH_SHA" "$LOCAL_PATCH"
  git -C "$NODE_ROOT" apply "$LOCAL_PATCH"
else
  echo "Required local compatibility patch is not applied" >&2
  exit 1
fi
[[ "$(git -C "$NODE_ROOT" rev-parse HEAD)" == "$COMMIT" ]]

check_sha "$LICENSE_SHA" "$NODE_ROOT/LICENSE"
check_sha "$UPSTREAM_REQUIREMENTS_SHA" "$NODE_ROOT/requirements.txt"
check_sha "$LOCK_SHA" "$LOCKFILE"
check_sha "$LOCAL_PATCH_SHA" "$LOCAL_PATCH"
MODEL_ACTUAL="$(openssl dgst -sha256 "$MODEL_BLOB" | awk '{print $NF}')"
[[ "$MODEL_ACTUAL" == "$MODEL_SHA" ]] || { echo "SHA-256 mismatch: $MODEL_BLOB" >&2; exit 1; }

if [[ "$MODE" == "install" ]]; then
  "$UV_BIN" pip install --python "$COMFY_PYTHON" --require-hashes -r "$LOCKFILE"
fi
"$COMFY_PYTHON" -m py_compile "$NODE_ROOT/__init__.py" "$NODE_ROOT/nodes.py"
"$COMFY_PYTHON" - <<'PY'
from importlib.metadata import version
expected = {"openai-agents": "0.19.4", "openai": "2.53.0", "Pillow": "12.3.0", "numpy": "2.4.6"}
for package, wanted in expected.items():
    actual = version(package)
    if actual != wanted:
        raise SystemExit(f"version mismatch: {package}={actual}, expected {wanted}")
from agents import set_tracing_disabled
from agents.tracing import get_trace_provider
set_tracing_disabled(True)
if not get_trace_provider()._disabled:
    raise SystemExit("OpenAI Agents tracing disable verification failed")
PY

if [[ "$MODE" == "install" ]]; then
  ollama create qwen3-vl-h3-context-ir:latest -f "$PROJECT_ROOT/models/text/qwen3-vl-h3-context-ir.Modelfile"
fi
echo "H3 Context IR Agent supply chain verified and installed at $COMMIT"
