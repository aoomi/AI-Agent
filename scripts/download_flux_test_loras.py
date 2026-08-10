#!/usr/bin/env python3
"""下载并隔离登记 FLUX.1 Schnell GGUF Q8_0 候选测试 LoRA。"""

from __future__ import annotations

import hashlib
import json
import struct
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LORA_ROOT = ROOT / "models" / "loras"
INDEX = LORA_ROOT / "测试LoRA索引.json"
BASE_MODEL = "black-forest-labs/FLUX.1-dev"
LICENSES = {"apache-2.0", "creativeml-openrail-m", "mit", "openrail++"}

MODELS = [
    ("风格", "国风浅涂/风格LoRA", "风格_国风仙韵_FLUX1_仅测试", "Muapi/5-guofeng5-flux.1-lora", "5-guofeng5-flux.1-lora.safetensors"),
    ("风格", "国风厚涂/风格LoRA", "风格_油画仙韵_FLUX1_仅测试", "dtthanh/flux_oil_painting_lora", "flux-oilpainting1.3-00001.safetensors"),
    ("风格", "国风浅涂/风格LoRA", "风格_水墨仙韵_FLUX1_仅测试", "Muapi/zyd232-s-ink-style", "zyd232-s-ink-style.safetensors"),
    ("风格", "国风厚涂/风格LoRA", "风格_奇幻骑士仙境_FLUX1_仅测试", "Muapi/flux-fantasy-knights-by-hailoknight", "flux-fantasy-knights-by-hailoknight.safetensors"),
    ("风格", "国风浅涂/风格LoRA", "风格_古风肖像仙韵_FLUX1_仅测试", "Muapi/cg-gufeng-portrait-flux1.d-lora", "cg-gufeng-portrait-flux1.d-lora.safetensors"),
    ("女性", "国风浅涂/人物LoRA", "女性_汉服仙姝_FLUX1_仅测试", "Muapi/hanfu-chinese-girl-flux-lora-realistic-photography", "hanfu-chinese-girl-flux-lora-realistic-photography.safetensors"),
    ("女性", "国风浅涂/人物LoRA", "女性_清颜仙姝_FLUX1_仅测试", "Muapi/zyd232-s-chinese-girl-lora-flux", "zyd232-s-chinese-girl-lora-flux.safetensors"),
    ("女性", "国风浅涂/人物LoRA", "女性_汉韵仙姝_FLUX1_仅测试", "Muapi/zyd232-s-hanfu-collection-female-flux.1-continuous-updating", "zyd232-s-hanfu-collection-female-flux.1-continuous-updating.safetensors"),
    ("男性", "国风浅涂/人物LoRA", "男性_亚洲仙君_FLUX1_仅测试", "Muapi/handsome-asian-boy", "handsome-asian-boy.safetensors"),
    ("男性", "国风厚涂/人物LoRA", "男性_俊逸仙君_FLUX1_仅测试", "Muapi/handsome-male-models-face-18-30-realism", "handsome-male-models-face-18-30-realism.safetensors"),
    ("男性", "国风浅涂/人物LoRA", "男性_全身仙君_FLUX1_仅测试", "strangerzonehf/FlatLay-Male-Model-LoRA-Demo", "Flat-Lay-Men-Model.safetensors"),
    ("灵兽", "国风厚涂/灵兽LoRA", "灵兽_巨龙仙兽_FLUX1_仅测试", "rzgar/mean-towering-dragon-lora-flux", "GOT_Dragon-000014.safetensors"),
    ("灵兽", "国风厚涂/灵兽LoRA", "灵兽_狼人仙兽_FLUX1_仅测试", "Muapi/werewolf-flux-sdxl-1.5", "werewolf-flux-sdxl-1.5.safetensors"),
    ("灵兽", "国风浅涂/灵兽LoRA", "灵兽_灵猫仙宠_FLUX1_仅测试", "Muapi/cat-magic-mcat-magic-citron-anime-treasure", "cat-magic-mcat-magic-citron-anime-treasure.safetensors"),
]


def model_info(repo: str) -> dict:
    request = urllib.request.Request(
        f"https://huggingface.co/api/models/{repo}",
        headers={"User-Agent": "AI-Agent-FLUX-LoRA-Test/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def verify_source(repo: str, source_file: str) -> tuple[str, str]:
    payload = model_info(repo)
    tags = set(payload.get("tags") or [])
    card = payload.get("cardData") or {}
    license_name = str(card.get("license") or "").strip().lower()
    card_base = str(card.get("base_model") or "").strip()
    tagged_bases = {
        tag.split(":", 1)[1]
        for tag in tags
        if tag.startswith("base_model:") and not tag.startswith("base_model:adapter:")
    }
    files = {
        str(item.get("rfilename") or "")
        for item in payload.get("siblings", [])
        if str(item.get("rfilename") or "").lower().endswith(".safetensors")
    }
    if license_name not in LICENSES:
        raise RuntimeError(f"测试许可门禁失败：{repo} ({license_name or '未声明'})")
    if card_base != BASE_MODEL or BASE_MODEL not in tagged_bases:
        raise RuntimeError(f"FLUX.1 底模双重门禁失败：{repo}")
    if source_file not in files:
        raise RuntimeError(f"源文件不存在：{repo}/{source_file}")
    return license_name, card_base


def download(repo: str, source_file: str, target: Path) -> None:
    if target.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(
        f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(source_file, safe='/')}",
        headers={"User-Agent": "AI-Agent-FLUX-LoRA-Test/1.0"},
    )
    with urllib.request.urlopen(request, timeout=900) as response, temporary.open("wb") as output:
        while block := response.read(8 * 1024 * 1024):
            output.write(block)
    temporary.replace(target)


def validate(path: Path) -> tuple[int, str]:
    with path.open("rb") as stream:
        header_size = struct.unpack("<Q", stream.read(8))[0]
        if not 2 < header_size <= 128 * 1024 * 1024:
            raise RuntimeError(f"Safetensors 头无效：{path}")
        header = json.loads(stream.read(header_size))
    keys = [key for key in header if key != "__metadata__"]
    markers = ("transformer", "double_blocks", "single_blocks", "lora_unet")
    if not keys or not all("lora" in key.lower() for key in keys):
        raise RuntimeError(f"非 LoRA 权重：{path}")
    if not any(any(marker in key.lower() for marker in markers) for key in keys):
        raise RuntimeError(f"非 FLUX LoRA 权重：{path}")
    return len(keys), hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    records = []
    counts: dict[str, int] = {}
    for kind, category, label, repo, source_file in MODELS:
        license_name, base_model = verify_source(repo, source_file)
        target = LORA_ROOT / category / f"{label}.safetensors"
        download(repo, source_file, target)
        tensor_count, digest = validate(target)
        counts[kind] = counts.get(kind, 0) + 1
        records.append({
            "kind": kind,
            "category": category,
            "filename": target.name,
            "source": f"https://huggingface.co/{repo}",
            "source_file": source_file,
            "license": license_name,
            "declared_base_model": base_model,
            "runtime_candidate": "FLUX.1 Schnell GGUF Q8_0",
            "size_bytes": target.stat().st_size,
            "sha256": digest,
            "tensor_count": tensor_count,
            "status": "仅测试，待逐项实图验收",
        })
    if counts != {"风格": 5, "女性": 3, "男性": 3, "灵兽": 3}:
        raise RuntimeError(f"分类数量不正确：{counts}")
    INDEX.write_text(json.dumps({
        "schema_version": "1.1",
        "count": len(records),
        "counts": counts,
        "production_enabled": False,
        "models": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(records), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
