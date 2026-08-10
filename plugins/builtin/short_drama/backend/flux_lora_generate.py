"""Generate one FLUX.1 image with a local LoRA on Apple Silicon."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from diffusers import FluxPipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="ModelsLab/flux.1-dev")
    parser.add_argument("--lora", required=True)
    parser.add_argument("--scale", type=float, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--guidance", type=float, default=3.5)
    parser.add_argument("--max-sequence-length", type=int, default=256)
    args = parser.parse_args()

    pipeline = FluxPipeline.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    pipeline.load_lora_weights(args.lora)
    pipeline.to("mps")
    image = pipeline(
        args.prompt,
        width=args.width,
        height=args.height,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        max_sequence_length=args.max_sequence_length,
        joint_attention_kwargs={"scale": args.scale},
    ).images[0]
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    del pipeline
    torch.mps.empty_cache()


if __name__ == "__main__":
    main()
