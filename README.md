# AI Video Generation System

A fully autonomous, multi-agent system that takes a topic and produces a published video across multiple social media platforms — end to end, no human intervention.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                │
│              (Master agent — sequential pipeline)                   │
└──────┬──────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────┐    ┌──────────────────────────────────────────────┐
│ StorylineAgent  │    │  Claude (claude-opus-4-8)                    │
│                 │───▶│  • Creative storyline, logline, full script  │
│  Agent 1        │    │  • Scene-by-scene visual descriptions        │
└────────┬────────┘    │  • Captions, descriptions, hashtags          │
         │             └──────────────────────────────────────────────┘
         ▼
┌─────────────────┐    ┌──────────────────────────────────────────────┐
│ VideoGeneration │    │  Concurrent Scene Swarm (asyncio.gather)     │
│ Agent           │───▶│  Scene 1 ──┐                                 │
│                 │    │  Scene 2 ──┼──▶ FFmpeg stitch → final.mp4   │
│  Agent 2        │    │  Scene N ──┘                                 │
└────────┬────────┘    │  Providers: RunwayML | Pika | LumaAI | Mock  │
         │             └──────────────────────────────────────────────┘
         ▼
┌─────────────────┐    ┌──────────────────────────────────────────────┐
│ SubtitleAgent   │    │  Concurrent Translation Swarm                │
│                 │───▶│  EN SRT → Spanish ──┐                       │
│  Agent 3        │    │          → French  ──┼──▶ .srt files        │
└────────┬────────┘    │          → Japanese──┘                       │
         │             │  Providers: DeepL | Claude fallback          │
         ▼             └──────────────────────────────────────────────┘
┌─────────────────┐    ┌──────────────────────────────────────────────┐
│ SocialMedia     │    │  Per-Platform Copy Generation                │
│ Agent           │───▶│  YouTube copy, TikTok hook, IG caption, etc  │
│                 │    │  Powered by Claude                           │
│  Agent 4        │    └──────────────────────────────────────────────┘
└────────┬────────┘
         ▼
┌─────────────────┐    ┌──────────────────────────────────────────────┐
│ Publishing      │    │  Concurrent Platform Swarm (asyncio.gather)  │
│ Agent           │───▶│  YouTube ──┐                                 │
│                 │    │  TikTok   ─┼──▶ Published! ✅               │
│  Agent 5        │    │  Instagram ┤                                 │
└─────────────────┘    │  Facebook  ┤                                 │
                       │  Twitter  ─┘                                 │
                       └──────────────────────────────────────────────┘
```

---

## Features

| # | Capability | Agent | Technology |
|---|-----------|-------|-----------|
| 1 | **Creative Storylines** | `StorylineAgent` | Claude claude-opus-4-8 |
| 2 | **AI Video Generation** | `VideoGenerationAgent` | RunwayML / Pika / LumaAI |
| 3 | **Multi-Language Subtitles** | `SubtitleAgent` | DeepL + Claude (10+ languages) |
| 4 | **Platform-Optimised Copy** | `SocialMediaAgent` | Claude claude-opus-4-8 |
| 5 | **Multi-Platform Publishing** | `PublishingAgent` | YouTube, TikTok, Instagram, Facebook, Twitter |

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API keys
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Run the demo (no API keys needed)
```bash
python main.py demo
```

### 4. Run with your own topic
```bash
python main.py run \
  --topic "Why Morning Routines Change Your Life" \
  --genre motivational \
  --audience "young professionals 25-40" \
  --duration 60 \
  --platforms youtube tiktok instagram
```

---

## CLI Reference

```
python main.py run          Run the full pipeline
python main.py demo         Quick demo with mock providers
python main.py list-platforms   Show all supported platforms
python main.py show-project <id>  Show project status
```

### `run` options

| Flag | Default | Description |
|------|---------|-------------|
| `--topic` | required | Video topic / concept |
| `--genre` | `general` | `documentary\|comedy\|drama\|educational\|motivational\|entertainment` |
| `--audience` | `general` | Target audience description |
| `--duration` | `60` | Total video length in seconds |
| `--platforms` | all | Space-separated: `youtube tiktok instagram facebook twitter` |
| `--skip-video` | false | Skip video generation (subtitles/publish still run) |
| `--project-id` | auto | Resume an existing project |

---

## Supported Platforms

| Platform | Max Duration | Notes |
|----------|-------------|-------|
| YouTube | 12 hours | Full HD, chapter markers |
| TikTok | 10 min | Vertical preferred |
| Instagram Reels | 60 min | Vertical preferred |
| Facebook | 4 hours | Wide format |
| Twitter/X | 2 min 20 sec | Short clips |

---

## Supported Subtitle Languages

`en` `es` `fr` `de` `ja` `zh` `ko` `pt` `ar` `hi` `it` `ru` `nl` `tr`

Configure via `SUBTITLE_LANGUAGES` in `.env`:
```
SUBTITLE_LANGUAGES=en,es,fr,de,ja,zh
```

---

## Video Generation Providers

Set `VIDEO_PROVIDER` in `.env`:

| Provider | Env Value | API Docs |
|----------|-----------|---------|
| RunwayML Gen-4 | `runwayml` | RunwayML API |
| Pika 2.0 | `pika` | Pika Labs API |
| LumaAI Dream Machine | `lumaai` | Luma AI API |
| Mock (no key needed) | `mock` | Local test stub |

---

## Project Structure

```
build-the-thing/
├── main.py                    # CLI entry point
├── config.py                  # Pydantic settings (reads .env)
├── requirements.txt
├── .env.example
│
├── agents/
│   ├── orchestrator.py        # Master pipeline coordinator
│   ├── storyline_agent.py     # Agent 1: Claude scriptwriter
│   ├── video_generation_agent.py  # Agent 2: Concurrent scene generator
│   ├── subtitle_agent.py      # Agent 3: SRT + translation swarm
│   ├── social_media_agent.py  # Agent 4: Platform copy writer
│   └── publishing_agent.py    # Agent 5: Concurrent publisher
│
├── tools/
│   ├── llm_tools.py           # Anthropic Claude API wrapper
│   ├── video_tools.py         # RunwayML / Pika / LumaAI / Mock
│   ├── subtitle_tools.py      # SRT gen + DeepL translation
│   ├── social_media_tools.py  # YouTube / TikTok / IG / FB / Twitter
│   └── file_tools.py          # Project state persistence
│
├── models/
│   ├── video_project.py       # VideoProject data model
│   └── platform_config.py     # Platform configs & PublishResult
│
├── utils/
│   ├── logger.py              # Rich-formatted logging
│   └── retry.py               # Async retry with exponential backoff
│
└── outputs/
    ├── videos/                # Generated video files
    ├── subtitles/             # SRT files per language
    └── logs/                  # Project JSON state + reports
```

---

## Agent Swarm Patterns

The system uses two concurrency patterns:

**Sequential pipeline** (Orchestrator): Each stage depends on the previous, so agents run in order.

**Concurrent swarm** (within agents): Independent sub-tasks run simultaneously via `asyncio.gather`:
- `VideoGenerationAgent`: All scenes generated in parallel
- `SubtitleAgent`: All language translations run in parallel  
- `PublishingAgent`: All platform uploads happen simultaneously

This means a 6-scene video with 5 subtitle languages published to 5 platforms runs `6 + 5 + 5 = 16` concurrent API calls within the pipeline.

---

## Environment Variables

See `.env.example` for the full list. Minimum required:

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Always required (storyline + subtitles)
VIDEO_PROVIDER=mock             # Use 'mock' to test without a video API
```
