"""Agent 2 — Video Generation
Generates each scene as a video clip then stitches them together.
Runs scene generation concurrently (swarm of async tasks).
"""
from __future__ import annotations
import asyncio
import os
from models.video_project import VideoProject, ProjectStatus
from tools.video_tools import VideoTools
from utils import get_logger

log = get_logger("VideoGenerationAgent")


class VideoGenerationAgent:
    """Spawns concurrent sub-tasks per scene, then stitches the final video."""

    name = "VideoGenerationAgent"

    def __init__(self) -> None:
        self.video_tools = VideoTools()

    async def run(self, project: VideoProject) -> VideoProject:
        log.info(
            f"[bold green]{self.name}[/] ▶ Generating {len(project.scenes)} scenes "
            f"via [bold]{self.video_tools.provider}[/]"
        )
        project.status = ProjectStatus.GENERATING_VIDEO
        project.mark_updated()

        # Concurrently generate all scene clips (swarm pattern)
        tasks = [
            self._generate_scene(project.project_id, scene.visual_description, scene.duration_seconds, scene.scene_number)
            for scene in project.scenes
        ]
        scene_paths_with_index = await asyncio.gather(*tasks)
        # Sort by scene number to preserve order
        scene_paths_with_index.sort(key=lambda x: x[0])
        scene_paths = [p for _, p in scene_paths_with_index]

        # Stitch scenes into one video
        final_path = os.path.join(
            self.video_tools.output_dir, f"{project.project_id}_final.mp4"
        )
        await self.video_tools.stitch_scenes(scene_paths, final_path)

        project.video_local_path = final_path
        log.info(f"[bold green]{self.name}[/] ✓ Final video: {final_path}")
        project.mark_updated()
        return project

    async def _generate_scene(
        self, project_id: str, prompt: str, duration: int, scene_num: int
    ) -> tuple[int, str]:
        scene_id = f"{project_id}_scene{scene_num:02d}"
        path = await self.video_tools.generate_video(
            visual_prompt=prompt,
            duration_seconds=duration,
            project_id=scene_id,
        )
        log.info(f"  Scene {scene_num:02d} generated → {os.path.basename(path)}")
        return scene_num, path
