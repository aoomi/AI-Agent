from pathlib import Path


APP = Path(__file__).resolve().parents[2] / "plugins/builtin/short_drama/frontend/App.vue"


def test_storyboard_resume_preserves_existing_shots_and_only_appends_missing() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "existingShots:StoryboardShot[] = []" in source
    assert "const existingByNumber = new Map(existingShots.map" in source
    assert "const existingShot = existingByNumber.get(index + 1);" in source
    assert "shots.push(existingShot);" in source
    assert "}, existingShots);" in source
    assert "storyboardShots.value = storyboardShots.value.filter(shot => shot.episode !== script.episode);\n        await createEpisodeStoryboard(project, script, controller, \"\", async shot =>" not in source
