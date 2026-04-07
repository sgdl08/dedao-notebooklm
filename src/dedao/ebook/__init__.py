"""电子书模块

提供电子书的 API 客户端和下载功能。
"""

from .client import EbookClient
from .downloader import (
    EbookDownloader,
    EbookDownloadResult,
    EbookDownloadProgress,
    download_ebook,
)

__all__ = [
    "EbookClient",
    "EbookDownloader",
    "EbookDownloadResult",
    "EbookDownloadProgress",
    "download_ebook",
]
