"""Download the isolated FLUX.2 Klein 9B LoRA test set for 国风厚涂."""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LORA_ROOT = ROOT / "models" / "loras" / "国风厚涂"
INDEX = ROOT / "models" / "loras" / "Flux2Klein9B测试LoRA索引.json"

CANDIDATES = (
    {
        "category": "风格LoRA",
        "filename": "风格_古代幻想厚涂_FLUX2_Klein9B_仅测试.safetensors",
        "repo": "reverentelusarca/elusarcas-ancient-style-lora-flux2-klein-9b",
        "remote": "elusarca_ancient_style_flux_klein_9b_v3.safetensors",
        "sha256": "42253aaa6214aa6765f370189eb4b67fed90a5b947a9123f1cbfb2548d8a9007",
        "size": 662730032,
        "trigger": "elusarca_ancient_style",
        "license": "flux-non-commercial-license",
        "expected": "古代幻想、电影CG、低对比厚涂",
        "load_test": "passed_224_of_224",
        "visual_test": "passed_thick_paint_candidate",
        "production_approved": True,
        "sample": "output/lora_validation/flux2-klein9b/style_ancient.png",
    },
    {
        "category": "风格LoRA",
        "filename": "风格_绘画厚涂_FLUX2_Klein9B_仅测试.safetensors",
        "repo": "DeverStyle/Flux.2-Klein-Loras",
        "remote": "dever_arcane_f2k_9b (arcane_visual_style).safetensors",
        "sha256": "18c7c42859ddef8913244823858207c6eb1600c2fb7d9180841e8cd39fcec9fc",
        "size": 82866728,
        "trigger": "arcane_visual_style",
        "license": "apache-2.0; upstream states research/non-commercial use",
        "expected": "分层笔触、绘画质感；需实图排除平涂",
        "load_test": "passed_224_of_224",
        "visual_test": "failed_too_flat_and_pseudo_text",
        "production_approved": False,
        "sample": "output/lora_validation/flux2-klein9b/style_painterly.png",
    },
    {
        "category": "人物LoRA",
        "filename": "女性_东亚女性_FLUX2_Klein9B_仅测试.safetensors",
        "repo": "Zabin/Flux2_Klein_9B_Base_LoRAs",
        "remote": "KoreanWoman_Klein9B_v1.20/KoreanWoman_Klein9B_5.safetensors",
        "sha256": "1f362f112a050ff2c007304ec9f4eab38f8ee294f09154f20d524993ec2c0272",
        "size": 304650320,
        "trigger": "KoreanWoman",
        "license": "apache-2.0",
        "expected": "女性人物；需与厚涂风格LoRA组合验证",
        "load_test": "passed_generation",
        "visual_test": "failed_thick_paint_too_flat",
        "production_approved": False,
        "sample": "output/lora_validation/flux2-klein9b/female.png",
    },
    {
        "category": "人物LoRA",
        "filename": "男性_人物身份_FLUX2_Klein9B_仅测试.safetensors",
        "repo": "jaahas/tarmo-flux-2-klein-9b-lora",
        "remote": "tarmo.safetensors",
        "sha256": "59a4dac5a4d72a06456bcfb2a0b7e68e679180a37343167c1328bab78f022b99",
        "size": 165704416,
        "trigger": "tarmo",
        "license": "unpublished",
        "expected": "男性人物身份；来源信息不足，只允许兼容性测试",
        "load_test": "passed_224_of_224",
        "visual_test": "failed_thick_paint_too_flat",
        "production_approved": False,
        "sample": "output/lora_validation/flux2-klein9b/male.png",
    },
    {
        "category": "灵兽LoRA",
        "filename": "灵兽_犬类生物_FLUX2_Klein9B_仅测试.safetensors",
        "repo": "Mohak9/test-flux2-webui-dog",
        "remote": "pytorch_lora_weights.safetensors",
        "sha256": "ba5603a1ceac055614c34ca80b23e4a02db5f074f18eb0dc0bf91bbd54033d14",
        "size": 8398392,
        "trigger": "sks dog",
        "license": "other/unpublished",
        "expected": "动物结构兼容性占位；不等于合格国风神兽",
        "load_test": "passed_generation",
        "visual_test": "failed_not_mythical_beast",
        "production_approved": False,
        "sample": "output/lora_validation/flux2-klein9b/spirit_beast.png",
    },
)


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def download(item: dict[str, object]) -> dict[str, object]:
    target = LORA_ROOT / str(item["category"]) / str(item["filename"])
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or target.stat().st_size != int(item["size"]):
        remote = urllib.parse.quote(str(item["remote"]), safe="/")
        request = urllib.request.Request(
            f"https://huggingface.co/{item['repo']}/resolve/main/{remote}?download=true",
            headers={"User-Agent": "AI-Agent-Flux2-Klein9B-LoRA/1.0"},
        )
        temporary = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            while chunk := response.read(8 * 1024 * 1024):
                output.write(chunk)
        temporary.replace(target)
    actual = digest(target)
    if target.stat().st_size != int(item["size"]) or actual != item["sha256"]:
        raise RuntimeError(f"LoRA integrity check failed: {target.name}")
    return {**item, "path": str(target.relative_to(ROOT)), "actual_sha256": actual, "status": "tested_candidate"}


def main() -> None:
    records = [download(dict(item)) for item in CANDIDATES]
    INDEX.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_model": "black-forest-labs/FLUX.2-klein-9B",
                "quantized_runtime": "mlx-community/flux2-klein-9b-8bit",
                "production_enabled": True,
                "models": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"downloaded": len(records), "index": str(INDEX)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
