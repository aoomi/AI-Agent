#!/usr/bin/env python3
"""下载并登记国风浅涂 / 柔光治愈仙侠淡彩风 SDXL LoRA。"""

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
CATEGORY_ROOT = "国风浅涂"
LEGACY_CATEGORY_ROOTS = {"国风浅涂柔光治愈仙侠淡彩风"}
BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"

STYLE = [
    ("国风浅涂_淡雅中国风插画_danya_zhongguofeng_chahua", "Muapi/sdxl-chinese-style-illustration", "openrail++"),
    ("国风浅涂_柔和水彩_rouhe_shuicai", "ntc-ai/SDXL-LoRA-slider.watercolor", "mit"),
    ("国风浅涂_仙气梦境_xianqi_mengjing", "ntc-ai/SDXL-LoRA-slider.dreamscape", "mit"),
    ("国风浅涂_空灵天使光_kongling_tianshiguang", "ntc-ai/SDXL-LoRA-slider.angelic", "mit"),
    ("国风浅涂_治愈幻想_zhiyu_huanxiang", "ntc-ai/SDXL-LoRA-slider.fantasy", "mit"),
]

PERSON = [
    ("空灵仙气_kongling_xianqi", "ntc-ai/SDXL-LoRA-slider.angelic"),
    ("仙侠幻想_xianxia_huanxiang", "ntc-ai/SDXL-LoRA-slider.fantasy"),
]

PERSON_BY_SEX = {
    "男性": [
        ("清逸出尘_qingyi_chuchen", "ntc-ai/SDXL-LoRA-slider.evocative"),
        ("温润清雅_wenrun_qingya", "ntc-ai/SDXL-LoRA-slider.friendly-smile"),
        ("浅染古风_qianran_gufeng", "ntc-ai/SDXL-LoRA-slider.watercolor"),
        ("漫光仙侠_manguang_xianxia", "ntc-ai/SDXL-LoRA-slider.cinematic-lighting"),
        ("淡墨清雅_danmo_qingya", "ming-yang/sdxl_chinese_ink_lora"),
        ("雾感仙姿_wugan_xianzi", "ntc-ai/SDXL-LoRA-slider.dreamscape"),
    ],
    "女性": [
        ("清柔仙韵_qingrou_xianyun", "ntc-ai/SDXL-LoRA-slider.angelic"),
        ("浅涂淡颜_qiantu_danyan", "ntc-ai/SDXL-LoRA-slider.watercolor"),
        ("雾感温婉_wugan_wenwan", "ntc-ai/SDXL-LoRA-slider.dreamscape"),
        ("清雅灵秀_qingya_lingxiu", "ntc-ai/SDXL-LoRA-slider.evocative"),
        ("柔光稚态_rouguang_zhitai", "ntc-ai/SDXL-LoRA-slider.very-very-very-cute"),
        ("淡彩仙姿_dancai_xianzi", "ntc-ai/SDXL-LoRA-slider.fantasy"),
    ],
}

SPIRIT_BEAST = [
    ("神话灵兽_shenhua_lingshou", "Muapi/mythical-creatures-lora-1.5-sdxl", "openrail++"),
    ("幼龙仙宠_youlong_xianchong", "Muapi/smol-dragons-lora-1.5-sdxl", "openrail++"),
    ("凶猛神龙_xiongmeng_shenlong", "ntc-ai/SDXL-LoRA-slider.ferocious-dragon", "mit"),
    ("月夜狼人_yueye_langren", "ntc-ai/SDXL-LoRA-slider.werewolf", "mit"),
    ("妖灵形态_yaoling_xingtai", "ntc-ai/SDXL-LoRA-slider.demon", "mit"),
    ("仙兽幻想_xianshou_huanxiang", "ntc-ai/SDXL-LoRA-slider.fantasy", "mit"),
    ("圣洁灵兽_shengjie_lingshou", "ntc-ai/SDXL-LoRA-slider.angelic", "mit"),
    ("灵力环绕_lingli_huanrao", "ntc-ai/SDXL-LoRA-slider.magical-energy-swirling-around", "mit"),
    ("龙族史诗_longzu_shishi", "ntc-ai/SDXL-LoRA-slider.dungeons-and-dragons-cover-artwork", "mit"),
    ("灵兽发光眼_lingshou_faguangyan", "ntc-ai/SDXL-LoRA-slider.glowing-eyes", "mit"),
    ("神圣白瞳_shensheng_baitong", "ntc-ai/SDXL-LoRA-slider.glowing-white-eyes", "mit"),
    ("鳞羽繁复_lin_yu_fanfu", "ntc-ai/SDXL-LoRA-slider.intricate", "mit"),
    ("灵兽动态骨骼_lingshou_dongtai_gugu", "ntc-ai/SDXL-LoRA-slider.dynamic-anatomy", "mit"),
    ("灵兽极致细节_lingshou_jizhi_xijie", "ntc-ai/SDXL-LoRA-slider.extremely-detailed", "mit"),
    ("毛羽微观肌理_maoyu_weiguan_jili", "ntc-ai/SDXL-LoRA-slider.micro-details-fine-details-detailed", "mit"),
    ("淡彩灵兽_dancai_lingshou", "ntc-ai/SDXL-LoRA-slider.watercolor", "mit"),
    ("梦境仙宠_mengjing_xianchong", "ntc-ai/SDXL-LoRA-slider.dreamscape", "mit"),
    ("幽光灵兽_youguang_lingshou", "ntc-ai/SDXL-LoRA-slider.cinematic-lighting-with-moody-ambiance", "mit"),
    ("雪境神兽_xuejing_shenshou", "ntc-ai/SDXL-LoRA-slider.snowingsnow-covered", "mit"),
    ("传说氛围_chuanshuo_fenwei", "ntc-ai/SDXL-LoRA-slider.evocative", "mit"),
]


def metadata(repo: str) -> tuple[str, str, int, str]:
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}", timeout=60) as response:
        payload = json.loads(response.read())
    tags = set(payload.get("tags") or [])
    license_name = next((tag.split(":", 1)[1] for tag in tags if tag.startswith("license:")), "")
    if license_name not in {"mit", "openrail", "openrail++", "creativeml-openrail-m"}:
        raise RuntimeError(f"模型未通过商用许可白名单：{repo} ({license_name or '未声明'})")
    siblings = [item.get("rfilename", "") for item in payload.get("siblings", [])]
    remote = next((name for name in siblings if name.lower().endswith(".safetensors")), "")
    if not remote:
        raise RuntimeError(f"模型没有 safetensors 权重：{repo}")
    card_data = payload.get("cardData") or {}
    base_model = str(card_data.get("base_model") or "").strip()
    tag_base_models = {
        tag.split(":", 1)[1]
        for tag in tags
        if tag.startswith("base_model:") and not tag.startswith("base_model:adapter:")
    }
    if base_model != BASE_MODEL or BASE_MODEL not in tag_base_models:
        raise RuntimeError(f"模型底模不兼容：{repo} ({base_model or '未声明'})")
    return remote, license_name, int(payload.get("downloads") or 0), base_model


def download(repo: str, remote: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{repo}/{remote}".encode()).hexdigest()[:20]
    target = CACHE / f"{key}.safetensors"
    if target.exists() and target.stat().st_size > 1_000_000:
        return target
    url = f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(remote)}?download=true"
    partial = target.with_suffix(".partial")
    subprocess.run(["curl", "-L", "--fail", "--retry", "8", "--retry-delay", "3", "--continue-at", "-", "--output", str(partial), url], check=True)
    partial.replace(target)
    return target


def install(category: str, label: str, repo: str, declared_license: str, sex: str = "") -> dict:
    remote, actual_license, downloads, base_model = metadata(repo)
    if actual_license != declared_license:
        declared_license = actual_license
    source = download(repo, remote)
    filename = f"{sex + '_' if sex else ''}{label}_{'nvxing_' if sex == '女性' else 'nanxing_' if sex == '男性' else ''}SDXL.safetensors"
    folder = LORA_ROOT / CATEGORY_ROOT / category
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    shutil.copy2(source, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {
        "category": f"{CATEGORY_ROOT}/{category}", "filename":filename, "path":str(target),
        "source":f"https://huggingface.co/{repo}", "source_file":remote, "base_model":base_model,
        "license":declared_license, "commercial_use":True, "downloads_at_selection":downloads,
        "size_bytes":target.stat().st_size, "sha256":digest,
    }


def retire_unlisted_person_loras(records: list[dict]) -> int:
    folder = LORA_ROOT / CATEGORY_ROOT / "人物LoRA"
    expected = {
        str(item["filename"])
        for item in records
        if item.get("category") == f"{CATEGORY_ROOT}/人物LoRA"
    }
    retired = CACHE / "retired_person_loras"
    moved = 0
    for path in sorted(folder.glob("*.safetensors")):
        if path.name in expected or "_仅测试" in path.stem:
            continue
        retired.mkdir(parents=True, exist_ok=True)
        target = retired / path.name
        if target.exists():
            target.unlink()
        path.replace(target)
        moved += 1
    return moved


def main() -> None:
    records = [install("风格LoRA", label, repo, license_name) for label, repo, license_name in STYLE]
    for sex in ("女性", "男性"):
        records.extend(install("人物LoRA", label, repo, "mit", sex) for label, repo in PERSON)
        records.extend(install("人物LoRA", label, repo, "mit", sex) for label, repo in PERSON_BY_SEX[sex])
    records.extend(install("灵兽LoRA", label, repo, license_name) for label, repo, license_name in SPIRIT_BEAST)
    retired_person_loras = retire_unlisted_person_loras(records)
    existing = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {"models":[]}
    replaced_roots = LEGACY_CATEGORY_ROOTS | {CATEGORY_ROOT}
    preserved = [
        item for item in existing.get("models", [])
        if not any(str(item.get("category", "")).startswith(f"{root}/") for root in replaced_roots)
    ]
    all_records = preserved + records
    CATALOG.write_text(json.dumps({"count":len(all_records), "models":all_records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = LORA_ROOT / CATEGORY_ROOT / "README.md"
    readme.write_text(
        "# 国风浅涂 / 柔光治愈仙侠淡彩风 LoRA 库\n\n"
        "- `风格LoRA/`：5个国风浅涂、柔光、淡彩、仙气风格LoRA。\n"
        "- `人物LoRA/`：8个女性人物LoRA、8个男性人物LoRA。\n"
        "- `灵兽LoRA/`：20个传说灵兽、神兽、仙宠和奇幻生物LoRA。\n"
        "- 人物目标：幼态圆脸、无辜大眼、浅淡眉眼、软萌温柔、浅色古装仙裙、干净发髻。\n"
        "- 画面目标：清透冷白、柔光大漫射、低饱和、轻肌理、无蜡像磨皮、高清真人短剧质感。\n"
        "- 文件统一使用中文、拼音检索名和SDXL底模标识。\n"
        "- 许可证、来源、下载量、文件大小和SHA-256见`../../商用LoRA索引.json`。\n"
        f"- 全部适配`{BASE_MODEL}`，模型许可为MIT、OpenRAIL++或CreativeML OpenRAIL-M。\n",
        encoding="utf-8",
    )
    print(json.dumps({"new_count":len(records), "style":5, "female":8, "male":8, "spirit_beast":20, "retired_person_loras":retired_person_loras, "catalog_total":len(all_records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
