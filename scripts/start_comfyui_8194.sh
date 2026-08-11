#!/bin/zsh
set -eu

comfy_root="/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI"
shared_root="/Users/aoo/AI/ComfyUI-Shared"
runtime_root="/Users/aoo/AI/Projects/ShortDramaPipeline"
export OPENAI_AGENTS_DISABLE_TRACING="1"
export PYTORCH_ENABLE_MPS_FALLBACK="1"

exec "$comfy_root/.venv/bin/python3" "$comfy_root/main.py" \
  --listen 127.0.0.1 --port 8194 --disable-auto-launch --disable-manager-ui \
  --disable-all-custom-nodes \
  --whitelist-custom-nodes \
    ComfyUI-QwenTTS comfyui_instantid ComfyUI_IPAdapter_plus ComfyUI-VideoHelperSuite \
    ComfyUI-Frame-Interpolation ComfyUI_FaceAnalysis ComfyUI-ReActor ComfyUI-MuseTalk \
    comfyui_controlnet_aux ComfyUI-GGUF ComfyUI_PuLID_Flux_ll ComfyUI-Flowty-TripoSR \
    ComfyUI-CUP ComfyUI_Bernini_Director comfyui-minimax-h3-context-ir-agent \
  --models-directory "$shared_root/models" \
  --extra-model-paths-config "/Users/aoo/AI/Tools/ComfyUI/main/extra_model_paths.yaml" \
  --input-directory "$shared_root/input" \
  --output-directory "$shared_root/output" \
  --temp-directory "$runtime_root/comfy/temp" \
  --user-directory "$runtime_root/comfy/user" \
  --database-url "sqlite:///$runtime_root/runs/comfyui_pipeline.db" \
  --cache-lru 8 --use-pytorch-cross-attention --log-stdout
