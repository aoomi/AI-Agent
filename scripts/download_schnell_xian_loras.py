#!/usr/bin/env python3
"""下载并登记可商用、兼容 FLUX.1 Schnell 的仙侠 LoRA。"""

from __future__ import annotations

import hashlib
import json
import struct
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LORA_ROOT = ROOT / "models" / "loras"
CATALOG = LORA_ROOT / "商用LoRA索引.json"
MODEL_INDEX = LORA_ROOT / "模型索引.json"
CATEGORY_ROOT = "国风浅涂"
BASE_MODEL = "black-forest-labs/FLUX.1-dev"
LICENSES = {"mit", "openrail++"}

MODELS = {
    "风格LoRA": [
        ("风格_暗夜仙境_FLUX1_Schnell_商用", "Muapi/flux-lora-dark-fantasy-80s-aesthetics-popular-on-tiktok", None),
        ("风格_流沙仙境_FLUX1_Schnell_商用", "Muapi/shadowed-sands-dark-fantasy-style-lora-flux", None),
        ("风格_幻彩仙境_FLUX1_Schnell_商用", "Muapi/artify-s-fantasy-and-sci-fi-art-flux-lora", None),
        ("风格_梦光仙境_FLUX1_Schnell_商用", "Muapi/midjourney-dreamlike-fantasy-flux-lora", None),
        ("风格_幽冥仙境_FLUX1_Schnell_商用", "Muapi/midjourney-dark-fantasy-flux-lora", None),
    ],
    "人物LoRA": [
        ("女性_汉服仙姝_FLUX1_Schnell_商用", "Muapi/hanfu-chinese-girl-flux-lora-realistic-photography", None),
        ("女性_清颜仙姝_FLUX1_Schnell_商用", "Muapi/zyd232-s-chinese-girl-lora-flux", None),
        ("女性_自然仙姝_FLUX1_Schnell_商用", "Muapi/chinese-girl-flux-1.d-lora-natural-realistic-photography", None),
        ("女性_灵秀仙姝_FLUX1_Schnell_商用", "Muapi/korean-girl-cute-face-flux-lora", None),
        ("女性_群芳仙姝_FLUX1_Schnell_商用", "Muapi/a-gaggle-of-generated-girls-flux.1-loras", None),
        ("男性_侧颜仙君_FLUX1_Schnell_商用", "Muapi/side-face-portrait-photography-under-light-flux1.d-lora", None),
        ("男性_未来仙君_FLUX1_Schnell_商用", "Muapi/flux-futuristic-portraits-lora", None),
        ("男性_写实仙君_FLUX1_Schnell_商用", "alexbalrus/flux-lora-portrait", "RBStyle_V2.safetensors"),
        ("男性_古风仙君_FLUX1_Schnell_商用", "Muapi/cg-gufeng-portrait-flux1.d-lora", None),
    ],
    "灵兽LoRA": [
        ("宠物_绒萌仙宠_FLUX1_Schnell_商用", "Muapi/plush-cute-animated-animals-flux1.d-lora", None),
        ("宠物_巨龙仙宠_FLUX1_Schnell_商用", "rzgar/mean-towering-dragon-lora-flux", "GOT_Dragon-000014.safetensors"),
        ("宠物_暗夜仙宠_FLUX1_Schnell_商用", "Muapi/children-of-the-night-horror-creatures-flux-lora", None),
        ("宠物_道场仙猫_FLUX1_Schnell_商用", "je-suis-tm/dojo_cat_lora_flux_nf4", "pytorch_lora_weights.safetensors"),
        ("宠物_线绘仙猫_FLUX1_Schnell_商用", "Muapi/cute-line-cat-emoji-flux1.d-lora", None),
    ],
}


def api_model(repo: str) -> dict:
    request = urllib.request.Request(f"https://huggingface.co/api/models/{repo}", headers={"User-Agent": "AI-Agent-LoRA-Installer/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def verified_metadata(repo: str, requested_file: str | None) -> tuple[str, str, int, str]:
    payload = api_model(repo)
    tags = set(payload.get("tags") or [])
    license_name = next((tag.split(":", 1)[1] for tag in tags if tag.startswith("license:")), "")
    card_base = str((payload.get("cardData") or {}).get("base_model") or "").strip()
    tagged_bases = {tag.split(":", 1)[1] for tag in tags if tag.startswith("base_model:") and not tag.startswith("base_model:adapter:")}
    if license_name not in LICENSES:
        raise RuntimeError(f"许可不允许进入商用库：{repo} ({license_name or '未声明'})")
    if card_base != BASE_MODEL or BASE_MODEL not in tagged_bases:
        raise RuntimeError(f"FLUX.1 底模双重校验失败：{repo} ({card_base}, {sorted(tagged_bases)})")
    safetensors = [item.get("rfilename", "") for item in payload.get("siblings", []) if str(item.get("rfilename", "")).lower().endswith(".safetensors")]
    remote = requested_file or (safetensors[0] if len(safetensors) == 1 else "")
    if not remote or remote not in safetensors:
        raise RuntimeError(f"Safetensors 文件选择不唯一或不存在：{repo} ({safetensors})")
    return remote, license_name, int(payload.get("downloads") or 0), card_base


def download(repo: str, remote: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(
        f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(remote, safe='/')}",
        headers={"User-Agent": "AI-Agent-LoRA-Installer/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as stream:
        while block := response.read(8 * 1024 * 1024):
            stream.write(block)
    temporary.replace(target)


def validate_safetensors(path: Path) -> int:
    with path.open("rb") as stream:
        header_size = struct.unpack("<Q", stream.read(8))[0]
        if header_size <= 2 or header_size > 128 * 1024 * 1024:
            raise RuntimeError(f"Safetensors 头无效：{path.name}")
        header = json.loads(stream.read(header_size))
    tensor_keys = [key for key in header if key != "__metadata__"]
    flux_markers = ("transformer", "double_blocks", "single_blocks", "lora_unet")
    if not tensor_keys or not any(any(marker in key.lower() for marker in flux_markers) for key in tensor_keys):
        raise RuntimeError(f"权重不含可识别 FLUX LoRA 键：{path.name}")
    if not any("lora" in key.lower() for key in tensor_keys):
        raise RuntimeError(f"权重不是 LoRA 适配器：{path.name}")
    return len(tensor_keys)


def main() -> None:
    records = []
    for category, items in MODELS.items():
        for label, repo, requested_file in items:
            remote, license_name, downloads, base_model = verified_metadata(repo, requested_file)
            target = LORA_ROOT / CATEGORY_ROOT / category / f"{label}.safetensors"
            if not target.is_file():
                download(repo, remote, target)
            tensor_count = validate_safetensors(target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            records.append({
                "category": f"{CATEGORY_ROOT}/{category}", "filename": target.name, "path": str(target),
                "source": f"https://huggingface.co/{repo}", "source_file": remote, "base_model": base_model,
                "runtime_base_model": "black-forest-labs/FLUX.1-schnell", "license": license_name,
                "commercial_use": True, "downloads_at_selection": downloads, "size_bytes": target.stat().st_size,
                "sha256": digest, "tensor_count": tensor_count,
            })
    if len(records) != 20:
        raise RuntimeError(f"安装数量不正确：{len(records)}")
    CATALOG.write_text(json.dumps({"count": 20, "models": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    styles = [
        {"display_name": item["filename"].removesuffix(".safetensors"), "file": str(Path(item["path"]).relative_to(LORA_ROOT)),
         "source": item["source"], "license": item["license"], "trigger_words": ["仙侠", "国风浅涂"],
         "size_bytes": item["size_bytes"], "sha256": item["sha256"]}
        for item in records if item["category"].endswith("/风格LoRA")
    ]
    MODEL_INDEX.write_text(json.dumps({"schema_version": "1.0", "base_model": "black-forest-labs/FLUX.1-schnell", "styles": styles}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": 20, "style": 5, "female": 5, "male": 5, "pet": 5}, ensure_ascii=False))


if __name__ == "__main__":
    main()
