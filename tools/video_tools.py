"""Video generation tool — supports RunwayML, Pika, LumaAI, and mock mode."""
from __future__ import annotations
import asyncio
import os
import time
import uuid
import httpx
from config import settings
from utils import get_logger, with_retry

log = get_logger("video_tools")


class VideoTools:
    def __init__(self) -> None:
        self.provider = settings.video_provider.lower()
        self.output_dir = os.path.join(settings.output_dir, "videos")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_video(
        self,
        visual_prompt: str,
        duration_seconds: int = 5,
        project_id: str | None = None,
    ) -> str:
        """Generate a video clip and return the local file path."""
        project_id = project_id or str(uuid.uuid4())
        log.info(f"[cyan]Generating video[/] via [bold]{self.provider}[/] ({duration_seconds}s)")

        if self.provider == "runwayml":
            return await self._generate_runwayml(visual_prompt, duration_seconds, project_id)
        elif self.provider == "pika":
            return await self._generate_pika(visual_prompt, duration_seconds, project_id)
        elif self.provider == "lumaai":
            return await self._generate_lumaai(visual_prompt, duration_seconds, project_id)
        else:
            return await self._generate_mock(visual_prompt, duration_seconds, project_id)

    # ── RunwayML ─────────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=2.0)
    async def _generate_runwayml(
        self, prompt: str, duration: int, project_id: str
    ) -> str:
        headers = {
            "Authorization": f"Bearer {settings.runwayml_api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }
        payload = {
            "promptText": prompt,
            "model": "gen4_turbo",
            "duration": min(duration, 10),
            "ratio": "1280:720",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.dev.runwayml.com/v1/image_to_video",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            task_id = resp.json()["id"]
            log.info(f"RunwayML task created: {task_id}")

            # Poll until done
            for _ in range(60):
                await asyncio.sleep(5)
                poll = await client.get(
                    f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                    headers=headers,
                )
                poll.raise_for_status()
                data = poll.json()
                status = data.get("status")
                if status == "SUCCEEDED":
                    video_url = data["output"][0]
                    return await self._download_video(video_url, project_id, client)
                elif status == "FAILED":
                    raise RuntimeError(f"RunwayML generation failed: {data}")

        raise TimeoutError("RunwayML generation timed out")

    # ── Pika ─────────────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=2.0)
    async def _generate_pika(
        self, prompt: str, duration: int, project_id: str
    ) -> str:
        headers = {
            "Authorization": f"Bearer {settings.pika_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "promptText": prompt,
            "duration": min(duration, 10),
            "frameRate": 24,
            "resolution": "1080p",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.pika.art/v2/generate",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            video_url = data.get("video_url") or data.get("url")
            if video_url:
                return await self._download_video(video_url, project_id, client)
        raise RuntimeError("Pika: no video URL returned")

    # ── LumaAI ───────────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=2.0)
    async def _generate_lumaai(
        self, prompt: str, duration: int, project_id: str
    ) -> str:
        headers = {
            "Authorization": f"Bearer {settings.lumaai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "loop": False,
        }
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                "https://api.lumalabs.ai/dream-machine/v1/generations",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            gen_id = resp.json()["id"]
            log.info(f"LumaAI generation started: {gen_id}")

            for _ in range(60):
                await asyncio.sleep(5)
                poll = await client.get(
                    f"https://api.lumalabs.ai/dream-machine/v1/generations/{gen_id}",
                    headers=headers,
                )
                poll.raise_for_status()
                data = poll.json()
                state = data.get("state")
                if state == "completed":
                    video_url = data["assets"]["video"]
                    return await self._download_video(video_url, project_id, client)
                elif state == "failed":
                    raise RuntimeError(f"LumaAI generation failed: {data}")

        raise TimeoutError("LumaAI generation timed out")

    # ── Mock ─────────────────────────────────────────────────────────────────

    async def _generate_mock(
        self, prompt: str, duration: int, project_id: str
    ) -> str:
        log.info("[yellow]MOCK[/] video generation (no API keys configured)")
        await asyncio.sleep(0.5)
        path = os.path.join(self.output_dir, f"{project_id}_mock.mp4")
        with open(path, "wb") as f:
            # Write minimal valid MP4 header bytes (ftyp box) for testing
            f.write(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41")
        log.info(f"Mock video saved: {path}")
        return path

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _download_video(
        self, url: str, project_id: str, client: httpx.AsyncClient
    ) -> str:
        path = os.path.join(self.output_dir, f"{project_id}_{int(time.time())}.mp4")
        async with client.stream("GET", url, timeout=300) as stream:
            stream.raise_for_status()
            with open(path, "wb") as f:
                async for chunk in stream.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
        log.info(f"Video downloaded: {path}")
        return path

    async def stitch_scenes(self, scene_paths: list[str], output_path: str) -> str:
        """Concatenate scene MP4 files into a single video using ffmpeg."""
        if len(scene_paths) == 1:
            import shutil
            shutil.copy(scene_paths[0], output_path)
            return output_path

        list_file = output_path.replace(".mp4", "_list.txt")
        with open(list_file, "w") as f:
            for p in scene_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        os.unlink(list_file)

        if proc.returncode != 0:
            log.warning(f"ffmpeg stitch warning: {stderr.decode()[-500:]}")
        log.info(f"Stitched video: {output_path}")
        return output_path
