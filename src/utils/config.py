"""Configuration helpers for dedao-notebooklm."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def default_data_root() -> Path:
    """Return the cross-platform external data root."""
    documents_dir = Path.home() / "Documents"
    base_dir = documents_dir if documents_dir.exists() else Path.home()
    return base_dir / "dedao-notebooklm-data"


def default_download_dir() -> Path:
    return default_data_root() / "downloads"


def default_ppt_dir() -> Path:
    return default_data_root() / "ppts"


@dataclass
class Config:
    """Application configuration."""

    dedao_cookie: str = ""
    download_dir: str = str(default_download_dir())
    ppt_dir: str = str(default_ppt_dir())
    max_workers: int = 5
    download_audio: bool = True
    generate_pdf: bool = False
    log_level: str = "INFO"
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default_path(cls) -> Path:
        return Path.home() / ".dedao-notebooklm" / "config.json"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        path = path or cls.default_path()
        if not path.exists():
            logger.debug("Config file does not exist, using defaults: %s", path)
            return cls()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**data)
        except Exception as exc:
            logger.warning("Failed to load config %s, using defaults: %s", path, exc)
            return cls()

    def save(self, path: Optional[Path] = None) -> None:
        path = path or self.default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Config saved: %s", path)

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.extra[key] = value


_global_config: Optional[Config] = None


def get_config(path: Optional[Path] = None) -> Config:
    global _global_config
    if _global_config is None:
        _global_config = Config.load(path)
    return _global_config


def set_config(config: Config) -> None:
    global _global_config
    _global_config = config


def load_config(path: Optional[Path] = None) -> Config:
    config = Config.load(path)
    set_config(config)
    return config
