"""Agent 3 — Subtitle Generator
Creates SRT subtitles in multiple languages concurrently (swarm of translation tasks).
"""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from models.video_project import VideoProject, ProjectStatus, SubtitleTrack
from tools.subtitle_tools import SubtitleTools, LANGUAGE_NAMES
from tools.llm_tools import LLMTools
from config import settings
from utils import get_logger

log = get_logger("SubtitleAgent")


class SubtitleAgent:
    """Generates base SRT then fans out translation to all target languages in parallel."""

    name = "SubtitleAgent"

    def __init__(self) -> None:
        self.llm = LLMTools()
        self.subtitle_tools = SubtitleTools(llm_tools=self.llm)

    async def run(self, project: VideoProject) -> VideoProject:
        languages = settings.subtitle_language_list
        log.info(
            f"[bold green]{self.name}[/] ▶ Generating subtitles in "
            f"{len(languages)} language(s): {', '.join(languages)}"
        )
        project.status = ProjectStatus.ADDING_SUBTITLES
        project.mark_updated()

        # Step 1: Generate base English SRT
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            en_srt_path = await loop.run_in_executor(
                pool,
                self.subtitle_tools.generate_srt_from_script,
                project.full_script,
                project.duration_seconds,
                project.project_id,
            )

        with open(en_srt_path, encoding="utf-8") as f:
            en_srt_content = f.read()

        project.subtitle_tracks.append(
            SubtitleTrack(
                language_code="en",
                language_name="English",
                srt_content=en_srt_content,
                file_path=en_srt_path,
            )
        )

        # Step 2: Translate to all non-English target languages concurrently
        non_en = [lang for lang in languages if lang != "en"]
        if non_en:
            translation_tasks = [
                self._translate(en_srt_content, lang, project.project_id)
                for lang in non_en
            ]
            tracks = await asyncio.gather(*translation_tasks)
            project.subtitle_tracks.extend(tracks)

        log.info(
            f"[bold green]{self.name}[/] ✓ {len(project.subtitle_tracks)} subtitle tracks created"
        )
        project.mark_updated()
        return project

    async def _translate(
        self, srt_content: str, language: str, project_id: str
    ) -> SubtitleTrack:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            path = await loop.run_in_executor(
                pool,
                self.subtitle_tools.translate_srt,
                srt_content,
                language,
                project_id,
            )
        with open(path, encoding="utf-8") as f:
            translated = f.read()
        return SubtitleTrack(
            language_code=language,
            language_name=LANGUAGE_NAMES.get(language, language),
            srt_content=translated,
            file_path=path,
        )
