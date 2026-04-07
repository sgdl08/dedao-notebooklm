# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Install project in editable mode
python3 -m pip install -e .

# Install with dev dependencies
python3 -m pip install -e ".[dev]"

# Run tests
python3 -m pytest tests/ -v

# Run single test file
python3 -m pytest tests/test_dedao.py -v

# Run single test
python3 -m pytest tests/test_dedao.py::TestCourseModel::test_course_creation -v

# Code formatting
python3 -m black src/
python3 -m ruff check src/

# CLI usage (after install)
dedao-nb --help
dedao-nb login --cookie "your-cookie"
dedao-nb list-courses
```

## Architecture

This project downloads courses from Dedao (得到) and converts them to Markdown format.

### Core Modules

```
src/
├── cli.py              # Click CLI entry point (dedao-nb)
├── dedao/              # Dedao API client
│   ├── client.py       # Main API client (courses, chapters)
│   ├── auth.py         # Cookie & QR code authentication
│   ├── models.py       # Dataclasses: Course, Chapter, Audiobook, Ebook, etc.
│   ├── downloader.py   # Concurrent chapter downloader
│   ├── audiobook.py    # Audiobook API client
│   ├── ebook.py        # Ebook API client (AES decryption)
│   ├── channel.py      # Channel/学习圈 API
│   ├── topic.py        # Topic API
│   ├── cache.py        # SQLite-based caching
│   └── account.py      # Multi-account management
├── converter/
│   ├── html_to_md.py   # HTML to Markdown converter
│   └── epub_generator.py # EPUB file generator
└── utils/
    ├── config.py       # Config management (~/.dedao-notebooklm/config.json)
    ├── crypto.py       # AES-CBC decryption (for ebooks)
    └── ffmpeg.py       # FFmpeg utilities
```

### Key Patterns

- **Authentication**: Cookie-based. Stored in `~/.dedao-notebooklm/config.json`. Use `get_current_cookie()` from `dedao.account` to get active account's cookie.
- **API Clients**: Each content type has its own client class (`DedaoClient`, `AudiobookClient`, `EbookClient`, etc.). All accept optional `cookie` parameter.
- **Caching**: SQLite cache at `~/.dedao-notebooklm/cache/cache.db`. Use `cache_get()`/`cache_set()` helpers.
- **Lazy imports**: Sub-module clients use factory functions (`get_audiobook_client()`, etc.) to avoid circular imports.

## Configuration

Config file: `~/.dedao-notebooklm/config.json`

```json
{
  "dedao_cookie": "...",
  "download_dir": "./downloads",
  "max_workers": 5
}
```

## Entry Point

`pyproject.toml` defines: `dedao-nb = "cli:main"` (note: `cli` not `src.cli` because packages are found in `src/`)
