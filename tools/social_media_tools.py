"""Social media upload and publishing tools for all platforms."""
from __future__ import annotations
import asyncio
import os
import httpx
from config import settings
from models.platform_config import Platform, PublishResult
from utils import get_logger, with_retry

log = get_logger("social_media_tools")


class SocialMediaTools:

    # ── YouTube ──────────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=4.0)
    async def upload_youtube(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        caption: str = "",
        category_id: str = "22",
        privacy: str = "public",
    ) -> PublishResult:
        log.info("[red]YouTube[/]: uploading video…")

        if not settings.youtube_refresh_token:
            return self._mock_result(Platform.YOUTUBE, "youtube_mock_id_001")

        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2.credentials import Credentials

            creds = Credentials(
                token=None,
                refresh_token=settings.youtube_refresh_token,
                client_id=settings.youtube_client_id,
                client_secret=settings.youtube_client_secret,
                token_uri="https://oauth2.googleapis.com/token",
            )
            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": title,
                    "description": f"{caption}\n\n{description}",
                    "tags": tags,
                    "categoryId": category_id,
                },
                "status": {"privacyStatus": privacy},
            }
            media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
            request = youtube.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = None
            while response is None:
                _, response = request.next_chunk()

            video_id = response["id"]
            return PublishResult(
                platform=Platform.YOUTUBE,
                success=True,
                post_id=video_id,
                post_url=f"https://youtu.be/{video_id}",
            )
        except Exception as exc:
            log.error(f"YouTube upload error: {exc}")
            return PublishResult(platform=Platform.YOUTUBE, success=False, error=str(exc))

    # ── TikTok ───────────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=4.0)
    async def upload_tiktok(
        self, video_path: str, caption: str, hashtags: list[str]
    ) -> PublishResult:
        log.info("[cyan]TikTok[/]: uploading video…")

        if not settings.tiktok_access_token:
            return self._mock_result(Platform.TIKTOK, "tiktok_mock_id_001")

        try:
            full_caption = f"{caption} " + " ".join(f"#{t.lstrip('#')}" for t in hashtags)
            file_size = os.path.getsize(video_path)

            async with httpx.AsyncClient(timeout=120) as client:
                # Step 1: init upload
                init_resp = await client.post(
                    "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
                    headers={
                        "Authorization": f"Bearer {settings.tiktok_access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "source_info": {
                            "source": "FILE_UPLOAD",
                            "video_size": file_size,
                            "chunk_size": file_size,
                            "total_chunk_count": 1,
                        }
                    },
                )
                init_resp.raise_for_status()
                upload_url = init_resp.json()["data"]["upload_url"]
                publish_id = init_resp.json()["data"]["publish_id"]

                # Step 2: upload file
                with open(video_path, "rb") as vf:
                    await client.put(
                        upload_url,
                        content=vf.read(),
                        headers={
                            "Content-Type": "video/mp4",
                            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                        },
                    )

                # Step 3: publish
                pub_resp = await client.post(
                    "https://open.tiktokapis.com/v2/post/publish/video/init/",
                    headers={
                        "Authorization": f"Bearer {settings.tiktok_access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "post_info": {
                            "title": full_caption[:2200],
                            "privacy_level": "PUBLIC_TO_EVERYONE",
                            "disable_duet": False,
                            "disable_comment": False,
                            "disable_stitch": False,
                        },
                        "source_info": {"source": "PULL_FROM_URL"},
                    },
                )
                pub_resp.raise_for_status()
                return PublishResult(
                    platform=Platform.TIKTOK,
                    success=True,
                    post_id=publish_id,
                )
        except Exception as exc:
            log.error(f"TikTok upload error: {exc}")
            return PublishResult(platform=Platform.TIKTOK, success=False, error=str(exc))

    # ── Instagram ────────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=4.0)
    async def upload_instagram(
        self,
        video_path: str,
        caption: str,
        hashtags: list[str],
        video_url: str | None = None,
    ) -> PublishResult:
        log.info("[purple]Instagram[/]: uploading reel…")

        if not settings.instagram_access_token:
            return self._mock_result(Platform.INSTAGRAM, "ig_mock_id_001")

        try:
            full_caption = caption + "\n\n" + " ".join(f"#{t.lstrip('#')}" for t in hashtags)
            base_url = f"https://graph.facebook.com/v18.0/{settings.instagram_account_id}"
            token = settings.instagram_access_token

            async with httpx.AsyncClient(timeout=120) as client:
                # Must use video_url (public URL) — Instagram requires hosted video
                media_resp = await client.post(
                    f"{base_url}/media",
                    params={
                        "media_type": "REELS",
                        "video_url": video_url or "https://example.com/video.mp4",
                        "caption": full_caption,
                        "access_token": token,
                    },
                )
                media_resp.raise_for_status()
                creation_id = media_resp.json()["id"]

                # Wait for processing
                for _ in range(30):
                    await asyncio.sleep(5)
                    status_resp = await client.get(
                        f"https://graph.facebook.com/v18.0/{creation_id}",
                        params={"fields": "status_code", "access_token": token},
                    )
                    if status_resp.json().get("status_code") == "FINISHED":
                        break

                # Publish
                pub_resp = await client.post(
                    f"{base_url}/media_publish",
                    params={"creation_id": creation_id, "access_token": token},
                )
                pub_resp.raise_for_status()
                post_id = pub_resp.json()["id"]
                return PublishResult(
                    platform=Platform.INSTAGRAM, success=True, post_id=post_id
                )
        except Exception as exc:
            log.error(f"Instagram upload error: {exc}")
            return PublishResult(platform=Platform.INSTAGRAM, success=False, error=str(exc))

    # ── Facebook ─────────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=4.0)
    async def upload_facebook(
        self,
        video_path: str,
        title: str,
        description: str,
        video_url: str | None = None,
    ) -> PublishResult:
        log.info("[blue]Facebook[/]: uploading video…")

        if not settings.facebook_access_token:
            return self._mock_result(Platform.FACEBOOK, "fb_mock_id_001")

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v18.0/{settings.facebook_page_id}/videos",
                    data={
                        "title": title,
                        "description": description,
                        "file_url": video_url or "",
                        "access_token": settings.facebook_access_token,
                    },
                )
                resp.raise_for_status()
                post_id = resp.json()["id"]
                return PublishResult(
                    platform=Platform.FACEBOOK,
                    success=True,
                    post_id=post_id,
                    post_url=f"https://www.facebook.com/video/{post_id}",
                )
        except Exception as exc:
            log.error(f"Facebook upload error: {exc}")
            return PublishResult(platform=Platform.FACEBOOK, success=False, error=str(exc))

    # ── Twitter / X ──────────────────────────────────────────────────────────

    @with_retry(max_attempts=3, base_delay=4.0)
    async def upload_twitter(
        self, video_path: str, tweet_text: str
    ) -> PublishResult:
        log.info("[sky_blue1]Twitter/X[/]: uploading video…")

        if not settings.twitter_api_key:
            return self._mock_result(Platform.TWITTER, "twitter_mock_id_001")

        try:
            import requests
            from requests_oauthlib import OAuth1

            auth = OAuth1(
                settings.twitter_api_key,
                settings.twitter_api_secret,
                settings.twitter_access_token,
                settings.twitter_access_token_secret,
            )
            file_size = os.path.getsize(video_path)

            # INIT
            init = requests.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                data={
                    "command": "INIT",
                    "total_bytes": file_size,
                    "media_type": "video/mp4",
                    "media_category": "tweet_video",
                },
                auth=auth,
            )
            media_id = init.json()["media_id_string"]

            # APPEND
            with open(video_path, "rb") as vf:
                requests.post(
                    "https://upload.twitter.com/1.1/media/upload.json",
                    data={"command": "APPEND", "media_id": media_id, "segment_index": 0},
                    files={"media": vf},
                    auth=auth,
                )

            # FINALIZE
            requests.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                data={"command": "FINALIZE", "media_id": media_id},
                auth=auth,
            )

            # Tweet
            tweet_resp = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": tweet_text[:280], "media": {"media_ids": [media_id]}},
                auth=auth,
            )
            tweet_resp.raise_for_status()
            tweet_id = tweet_resp.json()["data"]["id"]
            return PublishResult(
                platform=Platform.TWITTER,
                success=True,
                post_id=tweet_id,
                post_url=f"https://twitter.com/i/web/status/{tweet_id}",
            )
        except Exception as exc:
            log.error(f"Twitter upload error: {exc}")
            return PublishResult(platform=Platform.TWITTER, success=False, error=str(exc))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mock_result(self, platform: Platform, mock_id: str) -> PublishResult:
        log.info(f"[yellow]MOCK[/] publish to {platform.value} (credentials not set)")
        return PublishResult(
            platform=platform,
            success=True,
            post_id=mock_id,
            post_url=f"https://mock.example.com/{platform.value}/{mock_id}",
        )
