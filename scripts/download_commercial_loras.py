#!/usr/bin/env python3
"""下载并登记允许商用的 SDXL LoRA。"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LORA_ROOT = ROOT / "models" / "loras"
CACHE = LORA_ROOT / ".commercial_download_cache"
CATALOG = LORA_ROOT / "商用LoRA索引.json"


STYLE = [
    ("国风厚涂_中国风插画_guofeng_houtu_zhongguofeng_chahua_SDXL.safetensors", "Muapi/sdxl-chinese-style-illustration", "sdxl-chinese-style-illustration.safetensors", "openrail++", 104),
    ("国风厚涂_中国水墨_guofeng_houtu_zhongguo_shuimo_SDXL.safetensors", "Muapi/sdxl-chinese-ink-painting", "sdxl-chinese-ink-painting.safetensors", "openrail++", 712),
    ("国风厚涂_史诗油画_guofeng_houtu_shishi_youhua_SDXL.safetensors", "ntc-ai/SDXL-LoRA-slider.epic-oil-painting", "epic oil painting.safetensors", "mit", 193),
    ("国风厚涂_油画质感_guofeng_houtu_youhua_zhigan_SDXL.safetensors", "ntc-ai/SDXL-LoRA-slider.oil-painting", "oil painting.safetensors", "mit", 331),
    ("国风厚涂_超写实插画_guofeng_houtu_chaoxieshi_chahua_SDXL.safetensors", "ntc-ai/SDXL-LoRA-slider.ultra-realistic-illustration", "ultra realistic illustration.safetensors", "mit", 277),
]

UNIVERSAL = {
    "亚洲面孔_yazhou_miankong": ("ntc-ai/SDXL-LoRA-slider.asian", "asian.safetensors", "mit", 274),
    "极致细节_jizhi_xijie": ("ntc-ai/SDXL-LoRA-slider.extremely-detailed", "extremely detailed.safetensors", "mit", 538),
    "电影光影_dianying_guangying": ("ntc-ai/SDXL-LoRA-slider.cinematic-lighting", "cinematic lighting.safetensors", "mit", 473),
    "微观细节_weiguan_xijie": ("ntc-ai/SDXL-LoRA-slider.micro-details-fine-details-detailed", "micro details, fine details, detailed.safetensors", "mit", 441),
    "动态骨骼_dongtai_gugu": ("ntc-ai/SDXL-LoRA-slider.dynamic-anatomy", "dynamic anatomy.safetensors", "mit", 346),
    "手部优化_shoubu_youhua": ("ntc-ai/SDXL-LoRA-slider.nice-hands", "nice hands.safetensors", "mit", 304),
    "超写实插画_chaoxieshi_chahua": ("ntc-ai/SDXL-LoRA-slider.ultra-realistic-illustration", "ultra realistic illustration.safetensors", "mit", 277),
    "漫画肖像_manhua_xiaoxiang": ("ntc-ai/SDXL-LoRA-slider.comic-portrait", "comic portrait.safetensors", "mit", 152),
}

MALE_EXTRA = {
    "深色肤质_shense_fuzhi": ("ntc-ai/SDXL-LoRA-slider.dark-skinned", "dark-skinned.safetensors", "mit", 165),
    "油画肖像_youhua_xiaoxiang": ("ntc-ai/SDXL-LoRA-slider.oil-painting", "oil painting.safetensors", "mit", 331),
}

FEMALE_EXTRA = {
    "妆容优化_zhuangrong_youhua": ("ntc-ai/SDXL-LoRA-slider.makeup", "makeup.safetensors", "mit", 224),
    "水彩肖像_shuicai_xiaoxiang": ("ntc-ai/SDXL-LoRA-slider.watercolor", "watercolor.safetensors", "mit", 188),
}


def download(repo: str, remote: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{repo}/{remote}".encode()).hexdigest()[:20]
    target = CACHE / f"{key}.safetensors"
    if target.exists() and target.stat().st_size > 1_000_000:
        return target
    url = f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(remote)}?download=true"
    partial = target.with_suffix(".partial")
    subprocess.run(
        ["curl", "-L", "--fail", "--retry", "8", "--retry-delay", "3", "--continue-at", "-", "--output", str(partial), url],
        check=True,
    )
    partial.replace(target)
    return target


def install(category: str, filename: str, repo: str, remote: str, license_name: str, downloads: int) -> dict:
    source = download(repo, remote)
    folder = LORA_ROOT / category
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    shutil.copy2(source, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {
        "category": category,
        "filename": filename,
        "path": str(target),
        "source": f"https://huggingface.co/{repo}",
        "source_file": remote,
        "base_model": "stabilityai/stable-diffusion-xl-base-1.0",
        "license": license_name,
        "commercial_use": True,
        "downloads_at_selection": downloads,
        "size_bytes": target.stat().st_size,
        "sha256": digest,
    }


def main() -> None:
    records = []
    for filename, repo, remote, license_name, downloads in STYLE:
        records.append(install("国风厚涂/风格LoRA", filename, repo, remote, license_name, downloads))
    for sex_cn, sex_py, extras in (("男性", "nanxing", MALE_EXTRA), ("女性", "nvxing", FEMALE_EXTRA)):
        for label, (repo, remote, license_name, downloads) in {**UNIVERSAL, **extras}.items():
            filename = f"{sex_cn}_{label}_{sex_py}_SDXL.safetensors"
            records.append(install("国风厚涂/人物LoRA", filename, repo, remote, license_name, downloads))
    CATALOG.write_text(json.dumps({"count": len(records), "models": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(records), "catalog": str(CATALOG)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
