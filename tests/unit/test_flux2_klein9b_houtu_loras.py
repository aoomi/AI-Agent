from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "models/loras/Flux2Klein9B测试LoRA索引.json"


def test_klein9b_houtu_catalog_integrity() -> None:
    catalog = json.loads(INDEX.read_text(encoding="utf-8"))
    assert catalog["quantized_runtime"] == "mlx-community/flux2-klein-9b-8bit"
    assert catalog["production_enabled"] is True
    assert len(catalog["models"]) == 5
    for item in catalog["models"]:
        path = ROOT / item["path"]
        assert path.is_file()
        assert path.stat().st_size == item["size"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert item["status"] == "tested_candidate"
        assert (ROOT / item["sample"]).is_file()
    assert sum(item["production_approved"] is True for item in catalog["models"]) == 1
    assert next(item for item in catalog["models"] if item["production_approved"] is True)["filename"].startswith("风格_古代幻想厚涂_")


def test_active_houtu_tree_has_no_flux1_weights() -> None:
    active = ROOT / "models/loras/国风厚涂"
    assert not list(active.glob("*LoRA/*FLUX1*.safetensors"))
    names = [path.name for path in active.glob("*LoRA/*.safetensors")]
    assert sum(name.startswith("女性_") for name in names) == 1
    assert sum(name.startswith("男性_") for name in names) == 1


def test_klein9b_houtu_loras_are_wired_into_generation() -> None:
    backend = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    assert 'KLEIN9B_TEST_LORA_INDEX_FILE = LORA_ROOT / "Flux2Klein9B测试LoRA索引.json"' in backend
    assert '"--lora-paths"' in backend
    assert '"--lora-scales"' in backend
    assert 'checked("女性_" if female else "男性_", "人物LoRA", 0.72)' in backend
    assert 'checked("灵兽_", "灵兽LoRA", 0.75)' in backend
    assert "body=body" in backend
    assert 'if parsed.path == "/api/characters/generate" and asset_phase == "baseline"' in backend
    assert 'image.baseline.klein9b' in backend
    assert '"国风厚涂":"风格_油画仙韵_FLUX1_仅测试.safetensors"' not in backend


def test_runtime_builds_gendered_klein9b_lora_command(monkeypatch, tmp_path: Path) -> None:
    source = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
    spec = importlib.util.spec_from_file_location("compat_server_klein9b_test", source)
    assert spec and spec.loader
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)

    monkeypatch.setattr(backend, "OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(backend, "_load_store", lambda: {"projects": [{"id": "p1", "style": "国风厚涂"}]})
    monkeypatch.setattr(backend, "_update_image_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend, "_require_memory", lambda *args, **kwargs: None)
    captured: list[str] = []

    def capture(_job_id: str, command: list[str], **_kwargs) -> None:
        captured.extend(command)

    monkeypatch.setattr(backend, "_run_image_process", capture)
    result = backend._generate_klein9b_asset_baseline(
        "female", "古代女剑客", 512, 768, job_id="job", body={"project_id": "p1", "asset_kind": "character", "character_gender": "女性"}
    )
    assert "--lora-paths" in captured
    assert "--lora-scales" in captured
    assert any("风格_古代幻想厚涂_" in value for value in captured)
    assert not any("女性_东亚女性_" in value for value in captured)
    assert not any("男性_人物身份_" in value for value in captured)
    assert len(result["loras"]) == 1
