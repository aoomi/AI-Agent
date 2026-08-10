"""One-shot MLX structured generation worker.

The process deliberately exits after a single request so unified-memory model
weights and Metal caches are released before the next heavy task starts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from mlx_vlm import apply_chat_template, generate, load


def _json_object(text: str) -> dict:
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    decoder = json.JSONDecoder()
    for index, character in enumerate(clean):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(clean[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("model output does not contain a JSON object")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    request = json.load(sys.stdin)
    prompt = str(request.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")
    model, processor = load(args.model)
    messages = [
        {"role": "system", "content": "只输出严格JSON对象，不要Markdown，不要解释。"},
        {"role": "user", "content": prompt},
    ]
    formatted = apply_chat_template(
        processor,
        model.config,
        messages,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    response = generate(
        model,
        processor,
        prompt=formatted,
        max_tokens=max(64, min(1536, int(request.get("max_tokens", 768)))),
        verbose=False,
    ).text
    sys.stdout.write(json.dumps(_json_object(response), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
