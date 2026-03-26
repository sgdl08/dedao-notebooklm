"""NotebookLM 适配层

封装 notebooklm-py，提供现有代码期望的接口。
"""

from .models import (
    EnhancedNotebookInfo,
    NotebookLibraryStats,
    NotebookInfo,
)
from .library import (
    EnhancedNotebookLibrary,
    NotebookLibrary,
)
from .browser import NotebookLMBrowser
from .api_client import NotebookLMAPIClient, NotebookAPIData
from .config import (
    DEFAULT_DATA_DIR,
    DEFAULT_STORAGE_STATE,
    DEFAULT_LIBRARY_PATH,
    BROWSER_ARGS,
    TYPING_WPM_MIN,
    TYPING_WPM_MAX,
    TYPING_DELAY_MIN_MS,
    TYPING_DELAY_MAX_MS,
    TYPING_LONG_PAUSE_PROBABILITY,
    TYPING_LONG_PAUSE_MIN_MS,
    TYPING_LONG_PAUSE_MAX_MS,
)

__all__ = [
    # 数据模型
    "EnhancedNotebookInfo",
    "NotebookLibraryStats",
    "NotebookInfo",
    "NotebookAPIData",
    # 本地库
    "EnhancedNotebookLibrary",
    "NotebookLibrary",
    # 浏览器/API 客户端
    "NotebookLMBrowser",
    "NotebookLMAPIClient",
    # 配置
    "DEFAULT_DATA_DIR",
    "DEFAULT_STORAGE_STATE",
    "DEFAULT_LIBRARY_PATH",
    "BROWSER_ARGS",
    "TYPING_WPM_MIN",
    "TYPING_WPM_MAX",
    "TYPING_DELAY_MIN_MS",
    "TYPING_DELAY_MAX_MS",
    "TYPING_LONG_PAUSE_PROBABILITY",
    "TYPING_LONG_PAUSE_MIN_MS",
    "TYPING_LONG_PAUSE_MAX_MS",
]
