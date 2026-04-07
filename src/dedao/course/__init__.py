"""课程模块

提供课程的 API 客户端和下载功能。
"""

from .client import CourseClient, DedaoClient
from .downloader import (
    CourseDownloader,
    DownloadProgress,
    DownloadResult,
    download_course,
)

__all__ = [
    "CourseClient",
    "DedaoClient",  # 向后兼容
    "CourseDownloader",
    "DownloadProgress",
    "DownloadResult",
    "download_course",
]
