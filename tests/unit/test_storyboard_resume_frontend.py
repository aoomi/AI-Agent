from pathlib import Path


APP = Path(__file__).resolve().parents[2] / "plugins/builtin/short_drama/frontend/App.vue"


def test_storyboard_resume_preserves_existing_shots_and_only_appends_missing() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "const existingShots:StoryboardShot[] = [...storyboardShots.value];" in source
    assert "function mergeStoryboardEpisodeResults(existingShots:StoryboardShot[]" in source
    assert "const preserved = existingShots.filter(shot => !replace.has(shot.episode));" in source
    assert "shots:existingShots" in source
    assert "response.result.generated_episodes || []" in source
    assert 'if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;' in source
    assert "storyboardShots.value = storyboardShots.value.filter(shot => shot.episode !== script.episode);\n        await createEpisodeStoryboard(project, script, controller, \"\", async shot =>" not in source
