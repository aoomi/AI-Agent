from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "plugins/builtin/short_drama/frontend/App.vue"
STYLES = ROOT / "plugins/builtin/short_drama/frontend/styles.css"


def test_asset_category_buttons_show_asset_item_totals() -> None:
    source = APP.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")

    assert "function assetCategoryImageTotal(category:AssetCategory)" in source
    assert 'if (category === "人物") return characterProfiles.value.length;' in source
    assert 'if (category === "道具") return propProfiles.value.length;' in source
    assert "return sceneProfiles.value.length;" in source
    assert "{{ assetCategoryImageTotal(category) }}" in source
    assert "共${assetCategoryImageTotal(category)}项资产" in source
    assert "min-width: 76px" in styles
    assert "white-space: nowrap" in styles
