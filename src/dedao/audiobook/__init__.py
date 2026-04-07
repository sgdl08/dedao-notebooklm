"""有声书模块

提供有声书的 API 客户端和下载功能。
"""

# 从旧模块导入（保持向后兼容）
from .._audiobook_legacy import (
    AudiobookClient,
    Audiobook,
    AudiobookChapter,
    AudiobookDetail,
)

__all__ = [
    "AudiobookClient",
    "Audiobook",
    "AudiobookChapter",
    "AudiobookDetail",
]
