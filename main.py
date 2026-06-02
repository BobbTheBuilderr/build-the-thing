#!/usr/bin/env python3
"""
AI Video Generation System — CLI Entry Point

Usage:
  python main.py run --topic "The Future of AI" --genre documentary --duration 90
  python main.py run --topic "Morning Routine" --platforms youtube tiktok instagram
  python main.py list-platforms
  python main.py show-project <project_id>
"""
from __future__ import annotations
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="aivideo",
    help="Complete AI Video Generation System — from story to social media.",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    topic: str = typer.Option(..., "--topic", "-t", help="Video topic or concept"),
    genre: str = typer.Option("general", "--genre", "-g", help="Genre: documentary|comedy|drama|educational|motivational|entertainment"),
    target_audience: str = typer.Option("general", "--audience", "-a", help="Target audience"),
    duration: int = typer.Option(60, "--duration", "-d", help="Target duration in seconds"),
    platforms: Optional[list[str]] = typer.Option(
        None, "--platforms", "-p",
        help="Platforms to publish to (youtube tiktok instagram facebook twitter)",
    ),
    skip_video: bool = typer.Option(False, "--skip-video", help="Skip video generation (use mock)"),
    project_id: Optional[str] = typer.Option(None, "--project-id", help="Resume existing project"),
) -> None:
    """Run the full AI video generation pipeline."""
    from dotenv import load_dotenv
    load_dotenv()

    from agents.orchestrator import Orchestrator
    from models.platform_config import Platform

    selected_platforms = None
    if platforms:
        platform_map = {p.value: p for p in Platform}
        selected_platforms = [platform_map[p.lower()] for p in platforms if p.lower() in platform_map]
        if not selected_platforms:
            console.print("[red]No valid platforms specified.[/]")
            raise typer.Exit(1)

    orchestrator = Orchestrator()
    asyncio.run(
        orchestrator.run(
            topic=topic,
            genre=genre,
            target_audience=target_audience,
            duration_seconds=duration,
            platforms=selected_platforms,
            project_id=project_id,
            skip_video=skip_video,
        )
    )


@app.command("list-platforms")
def list_platforms() -> None:
    """List all supported social media platforms."""
    from models.platform_config import Platform, PLATFORM_DEFAULTS

    table = Table(title="Supported Platforms", show_header=True)
    table.add_column("Platform", style="cyan")
    table.add_column("Max Duration")
    table.add_column("Max File Size")
    table.add_column("Vertical Video")

    for platform, cfg in PLATFORM_DEFAULTS.items():
        mins = cfg.max_duration_seconds // 60
        table.add_row(
            platform.value,
            f"{mins} min",
            f"{cfg.max_file_size_mb} MB",
            "Yes" if cfg.requires_vertical else "No",
        )
    console.print(table)


@app.command("show-project")
def show_project(
    project_id: str = typer.Argument(..., help="Project ID to display"),
) -> None:
    """Show status of an existing project."""
    from dotenv import load_dotenv
    load_dotenv()

    from tools.file_tools import FileTools
    ft = FileTools()
    project = ft.load_project(project_id)
    if not project:
        console.print(f"[red]Project {project_id!r} not found.[/]")
        raise typer.Exit(1)

    console.print(f"[bold]Project:[/] {project.project_id}")
    console.print(f"[bold]Title:[/] {project.title}")
    console.print(f"[bold]Status:[/] {project.status.value}")
    console.print(f"[bold]Scenes:[/] {len(project.scenes)}")
    console.print(f"[bold]Subtitles:[/] {[t.language_code for t in project.subtitle_tracks]}")

    if project.publish_results:
        table = Table(title="Publish Results")
        table.add_column("Platform")
        table.add_column("Success")
        table.add_column("URL")
        for r in project.publish_results:
            table.add_row(r.get("platform"), str(r.get("success")), r.get("post_url") or "")
        console.print(table)


@app.command("demo")
def demo() -> None:
    """Run a quick demo with mock providers (no API keys required)."""
    from dotenv import load_dotenv
    load_dotenv()

    import os
    os.environ.setdefault("VIDEO_PROVIDER", "mock")

    from agents.orchestrator import Orchestrator
    from models.platform_config import Platform

    console.print("[bold cyan]Running DEMO mode (mock video provider)[/]")
    orchestrator = Orchestrator()
    asyncio.run(
        orchestrator.run(
            topic="The Power of Human Connection in the Digital Age",
            genre="documentary",
            target_audience="young adults 18-35",
            duration_seconds=30,
            platforms=[Platform.YOUTUBE, Platform.TIKTOK, Platform.INSTAGRAM],
            skip_video=False,
        )
    )


if __name__ == "__main__":
    app()
