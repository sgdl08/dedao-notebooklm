"""配置管理模块"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """应用配置"""
    # 得到 Cookie
    dedao_cookie: str = ""

    # 下载目录
    download_dir: str = "./downloads"

    # 最大并发数
    max_workers: int = 5

    # 是否下载音频
    download_audio: bool = True

    # 是否生成 PDF
    generate_pdf: bool = False

    # 日志级别
    log_level: str = "INFO"

    # 其他配置
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default_path(cls) -> Path:
        """获取默认配置文件路径"""
        return Path.home() / ".dedao-notebooklm" / "config.json"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """从文件加载配置

        Args:
            path: 配置文件路径，默认使用默认路径

        Returns:
            Config 实例
        """
        path = path or cls.default_path()

        if not path.exists():
            logger.debug(f"配置文件不存在，使用默认配置：{path}")
            return cls()

        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return cls(**data)
        except Exception as e:
            logger.warning(f"读取配置失败：{e}，使用默认配置")
            return cls()

    def save(self, path: Optional[Path] = None):
        """保存配置到文件

        Args:
            path: 配置文件路径，默认使用默认路径
        """
        path = path or self.default_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        logger.info(f"配置已保存：{path}")

    def update(self, **kwargs):
        """更新配置

        Args:
            **kwargs: 要更新的配置项
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.extra[key] = value


# 全局配置实例
_global_config: Optional[Config] = None


def get_config(path: Optional[Path] = None) -> Config:
    """获取全局配置实例

    Args:
        path: 配置文件路径

    Returns:
        Config 实例
    """
    global _global_config
    if _global_config is None:
        _global_config = Config.load(path)
    return _global_config


def set_config(config: Config):
    """设置全局配置"""
    global _global_config
    _global_config = config


def load_config(path: Optional[Path] = None) -> Config:
    """重新加载配置

    Args:
        path: 配置文件路径

    Returns:
        Config 实例
    """
    config = Config.load(path)
    set_config(config)
    return config
