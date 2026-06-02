from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = "claude-opus-4-8"

    # Video providers
    video_provider: str = Field(default="mock", alias="VIDEO_PROVIDER")
    runwayml_api_key: str = Field(default="", alias="RUNWAYML_API_KEY")
    pika_api_key: str = Field(default="", alias="PIKA_API_KEY")
    lumaai_api_key: str = Field(default="", alias="LUMAAI_API_KEY")

    # Speech / Subtitle
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    deepl_api_key: str = Field(default="", alias="DEEPL_API_KEY")

    # YouTube
    youtube_client_id: str = Field(default="", alias="YOUTUBE_CLIENT_ID")
    youtube_client_secret: str = Field(default="", alias="YOUTUBE_CLIENT_SECRET")
    youtube_refresh_token: str = Field(default="", alias="YOUTUBE_REFRESH_TOKEN")

    # TikTok
    tiktok_client_key: str = Field(default="", alias="TIKTOK_CLIENT_KEY")
    tiktok_client_secret: str = Field(default="", alias="TIKTOK_CLIENT_SECRET")
    tiktok_access_token: str = Field(default="", alias="TIKTOK_ACCESS_TOKEN")

    # Instagram / Facebook
    instagram_access_token: str = Field(default="", alias="INSTAGRAM_ACCESS_TOKEN")
    instagram_account_id: str = Field(default="", alias="INSTAGRAM_ACCOUNT_ID")
    facebook_access_token: str = Field(default="", alias="FACEBOOK_ACCESS_TOKEN")
    facebook_page_id: str = Field(default="", alias="FACEBOOK_PAGE_ID")

    # Twitter / X
    twitter_api_key: str = Field(default="", alias="TWITTER_API_KEY")
    twitter_api_secret: str = Field(default="", alias="TWITTER_API_SECRET")
    twitter_access_token: str = Field(default="", alias="TWITTER_ACCESS_TOKEN")
    twitter_access_token_secret: str = Field(default="", alias="TWITTER_ACCESS_TOKEN_SECRET")

    # System
    output_dir: str = Field(default="outputs", alias="OUTPUT_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    subtitle_languages: str = Field(default="en,es,fr,de,ja", alias="SUBTITLE_LANGUAGES")

    @property
    def subtitle_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.subtitle_languages.split(",") if lang.strip()]


settings = Settings()
