"""Orchestrator — Master Agent
Coordinates the entire pipeline:
  StorylineAgent → VideoGenerationAgent → SubtitleAgent
                 → SocialMediaAgent     → PublishingAgent

The orchestrator uses a sequential pipeline for data-dependent stages,
and each agent internally spawns concurrent sub-tasks (swarm pattern).
"""
from __future__ import annotations
import asyncio
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from models.video_project import VideoProject, ProjectStatus
from models.platform_config import Platform
from agents.storyline_agent import StorylineAgent
from agents.video_generation_agent import VideoGenerationAgent
from agents.subtitle_agent import SubtitleAgent
from agents.social_media_agent import SocialMediaAgent
from agents.publishing_agent import PublishingAgent
from tools.file_tools import FileTools
from utils import get_logger

log = get_logger("Orchestrator")
console = Console()


class Orchestrator:
    """
    Master orchestrator that runs the full AI video production pipeline.

    Pipeline stages (sequential, each stage enables the next):
      1. StorylineAgent      — write creative script & scenes
      2. VideoGenerationAgent — generate & stitch video (concurrent scenes)
      3. SubtitleAgent       — create & translate SRT (concurrent languages)
      4. SocialMediaAgent    — craft per-platform copy
      5. PublishingAgent     — publish to all platforms (concurrent)
    """

    def __init__(self) -> None:
        self.storyline_agent = StorylineAgent()
        self.video_agent = VideoGenerationAgent()
        self.subtitle_agent = SubtitleAgent()
        self.social_agent = SocialMediaAgent()
        self.publishing_agent = PublishingAgent()
        self.file_tools = FileTools()

    async def run(
        self,
        topic: str,
        genre: str = "general",
        target_audience: str = "general",
        duration_seconds: int = 60,
        platforms: list[Platform] | None = None,
        project_id: str | None = None,
        skip_video: bool = False,
    ) -> VideoProject:
        platforms = platforms or list(Platform)
        project_id = project_id or str(uuid.uuid4())[:8]

        project = VideoProject(
            project_id=project_id,
            topic=topic,
            genre=genre,
            target_audience=target_audience,
            duration_seconds=duration_seconds,
        )

        self._print_header(project, platforms)

        try:
            # ── Stage 1: Storyline ────────────────────────────────────────
            project = self.storyline_agent.run(project)
            self.file_tools.save_project(project)
            self._checkpoint("Storyline", project)

            # ── Stage 2: Video Generation ─────────────────────────────────
            if not skip_video:
                project = await self.video_agent.run(project)
                self.file_tools.save_project(project)
                self._checkpoint("Video Generation", project)
            else:
                log.info("[yellow]Skipping video generation (skip_video=True)[/]")

            # ── Stage 3: Subtitles ────────────────────────────────────────
            project = await self.subtitle_agent.run(project)
            self.file_tools.save_project(project)
            self._checkpoint("Subtitles", project)

            # ── Stage 4: Social Media Copy ────────────────────────────────
            project = self.social_agent.run(project, platforms)
            self.file_tools.save_project(project)
            self._checkpoint("Social Media Copy", project)

            # ── Stage 5: Publish ──────────────────────────────────────────
            project = await self.publishing_agent.run(project, platforms)
            self.file_tools.save_project(project)

        except Exception as exc:
            log.error(f"[red]Pipeline failed at stage {project.status.value}: {exc}[/]")
            project.status = ProjectStatus.FAILED
            self.file_tools.save_project(project)
            raise

        # Save final report
        report_path = self.file_tools.save_report(project)
        self._print_summary(project, report_path)
        return project

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _print_header(self, project: VideoProject, platforms: list[Platform]) -> None:
        console.print(
            Panel.fit(
                f"[bold cyan]AI Video Generation Pipeline[/]\n"
                f"Topic: [yellow]{project.topic}[/]\n"
                f"Genre: {project.genre}  |  Audience: {project.target_audience}  |  Duration: {project.duration_seconds}s\n"
                f"Platforms: {', '.join(p.value for p in platforms)}",
                title="[bold]Orchestrator[/]",
                border_style="cyan",
            )
        )

    def _checkpoint(self, stage: str, project: VideoProject) -> None:
        log.info(f"[dim]── Checkpoint: {stage} complete ──[/]")

    def _print_summary(self, project: VideoProject, report_path: str) -> None:
        table = Table(title="Publish Results", show_header=True)
        table.add_column("Platform", style="cyan")
        table.add_column("Status")
        table.add_column("URL / Error")

        for r in project.publish_results:
            ok = r.get("success", False)
            table.add_row(
                r.get("platform", "?"),
                "✅ Success" if ok else "❌ Failed",
                r.get("post_url") or r.get("error") or "",
            )

        console.print()
        console.print(table)
        console.print(
            Panel.fit(
                f"[bold green]Pipeline Complete![/]\n"
                f"Project ID: [cyan]{project.project_id}[/]\n"
                f"Report: [dim]{report_path}[/]",
                border_style="green",
            )
        )
