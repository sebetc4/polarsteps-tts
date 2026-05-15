#!/usr/bin/env bash
#
# Starts the Voxtral TTS server via vllm-omni.
# Configuration validated for 24 GB VRAM GPU (RTX 5090 Laptop / 4090) — see
# docs/roadmap/etape-4-synthese-tts.md § Findings from smoke test.
#
# Usage:
#   ./scripts/serve-voxtral.sh            # default configuration
#   PORT=9000 ./scripts/serve-voxtral.sh  # override port
#
# The terminal remains blocked while the server is running (Ctrl+C to stop).

set -euo pipefail

VENV="${VOXTRAL_VENV:-$HOME/venvs/vllm-omni}"
MODEL_DIR="${VOXTRAL_MODEL_DIR:-/ai/models/tts/Voxtral-4B-TTS-2603}"
MODEL_NAME="${VOXTRAL_MODEL_NAME:-mistralai/Voxtral-4B-TTS-2603}"
PORT="${PORT:-8091}"
GPU_MEM="${GPU_MEM:-0.45}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"

if [[ ! -f "$VENV/bin/activate" ]]; then
  echo "Error: vllm-omni venv not found at $VENV" >&2
  echo "See docs/polarsteps-tts-guide.md § Installation for setup." >&2
  exit 1
fi

if [[ ! -d "$MODEL_DIR" ]]; then
  echo "Error: Voxtral model not found at $MODEL_DIR" >&2
  echo "huggingface-cli download $MODEL_NAME --local-dir $MODEL_DIR" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

# Sanity check: vllm and vllm-omni must have the same major/minor version.
# vllm-omni does not always track vllm in real-time — an unpinned pip install
# might grab vllm 0.21+ while vllm-omni is still on 0.20 → crash on server boot
# (missing abstract method). See polarsteps-tts-guide.md.
# We read the version via `pip show` rather than `python -c "import vllm"` because
# the import triggers NIXL logs that pollute stdout.
_extract_mm() {
  # No "exit" in awk: it closes the pipe and pip show dies with SIGPIPE,
  # which combined with `set -e` + `pipefail` silently kills the script.
  pip show "$1" 2>/dev/null \
    | awk '/^Version:/ {split($2, a, "."); print a[1]"."a[2]}'
}
_vllm_mm="$(_extract_mm vllm)"
_omni_mm="$(_extract_mm vllm-omni)"
if [[ -n "$_vllm_mm" && -n "$_omni_mm" && "$_vllm_mm" != "$_omni_mm" ]]; then
  echo "Error: vllm ($_vllm_mm) and vllm-omni ($_omni_mm) have different major/minor versions." >&2
  echo "Fix: pip install \"vllm==${_omni_mm}.*\" \"vllm-omni==${_omni_mm}.*\"" >&2
  exit 1
fi

export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

exec vllm serve "$MODEL_DIR" \
  --served-model-name "$MODEL_NAME" \
  --omni \
  --port "$PORT" \
  --gpu-memory-utilization "$GPU_MEM" \
  --max-model-len "$MAX_MODEL_LEN"
