"""File and project state management utilities."""
from __future__ import annotations
import json
import os
from datetime import datetime
from models.video_project import VideoProject
from utils import get_logger

log = get_logger("file_tools")


class FileTools:
    def __init__(self, output_dir: str = "outputs") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def save_project(self, project: VideoProject) -> str:
        path = os.path.join(self.output_dir, f"{project.project_id}_state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(project.model_dump(mode="json"), f, indent=2, default=str)
        return path

    def load_project(self, project_id: str) -> VideoProject | None:
        path = os.path.join(self.output_dir, f"{project_id}_state.json")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return VideoProject(**data)

    def save_report(self, project: VideoProject) -> str:
        path = os.path.join(self.output_dir, f"{project.project_id}_report.md")
        lines = [
            f"# Video Project Report",
            f"",
            f"**Project ID:** `{project.project_id}`",
            f"**Topic:** {project.topic}",
            f"**Status:** {project.status.value}",
            f"**Created:** {project.created_at}",
            f"",
            f"## Storyline",
            f"**Title:** {project.title}",
            f"**Logline:** {project.logline}",
            f"",
            f"### Full Script",
            f"```",
            project.full_script or "",
            f"```",
            f"",
            f"## Video",
            f"**Local path:** `{project.video_local_path}`",
            f"",
            f"## Subtitles",
        ]
        for track in project.subtitle_tracks:
            lines.append(f"- **{track.language_name}** (`{track.language_code}`): `{track.file_path}`")

        lines += [
            f"",
            f"## Social Media Caption",
            f"> {project.caption}",
            f"",
            f"**Hashtags:** " + " ".join(f"`#{h}`" for h in project.hashtags),
            f"",
            f"## Publish Results",
        ]
        for r in project.publish_results:
            status = "✅" if r.get("success") else "❌"
            lines.append(f"- {status} **{r.get('platform')}**: {r.get('post_url') or r.get('error')}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log.info(f"Report saved: {path}")
        return path
