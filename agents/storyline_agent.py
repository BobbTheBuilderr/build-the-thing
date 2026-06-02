"""Agent 1 — Storyline Writer
Responsible for generating creative scripts, scenes, captions, and hashtags.
"""
from __future__ import annotations
from models.video_project import VideoProject, ProjectStatus, SceneScript
from tools.llm_tools import LLMTools
from utils import get_logger

log = get_logger("StorylineAgent")


class StorylineAgent:
    """Uses Claude to write a complete, structured video storyline."""

    name = "StorylineAgent"

    def __init__(self) -> None:
        self.llm = LLMTools()

    def run(self, project: VideoProject) -> VideoProject:
        log.info(
            f"[bold green]{self.name}[/] ▶ Writing storyline for: [italic]{project.topic}[/]"
        )
        project.status = ProjectStatus.WRITING_STORYLINE
        project.mark_updated()

        storyline = self.llm.write_storyline(
            topic=project.topic,
            genre=project.genre,
            target_audience=project.target_audience,
            duration_seconds=project.duration_seconds,
        )

        project.title = storyline.get("title", project.topic)
        project.logline = storyline.get("logline", "")
        project.full_script = storyline.get("full_script", "")
        project.caption = storyline.get("caption", "")
        project.description = storyline.get("description", "")
        project.hashtags = storyline.get("hashtags", [])

        raw_scenes = storyline.get("scenes", [])
        project.scenes = [
            SceneScript(
                scene_number=s.get("scene_number", i + 1),
                title=s.get("title", f"Scene {i + 1}"),
                narration=s.get("narration", ""),
                visual_description=s.get("visual_description", ""),
                duration_seconds=s.get("duration_seconds", 5),
                mood=s.get("mood", "neutral"),
            )
            for i, s in enumerate(raw_scenes)
        ]

        log.info(
            f"[bold green]{self.name}[/] ✓ Title: [italic]{project.title}[/] "
            f"| {len(project.scenes)} scenes"
        )
        project.mark_updated()
        return project
