"""得到 (Dedao) 模块

提供得到 App 内容的下载功能。

主要组件：
- BaseClient: 基础 HTTP 客户端
- course: 课程模块 (CourseClient, CourseDownloader)
- ebook: 电子书模块 (EbookClient, EbookDownloader)
"""

# 基础类
from .base import BaseClient, DedaoAPIError, DedaoNetworkError, DedaoAuthError
from .auth import DedaoAuth, get_cookie_from_chrome
from .constants import ContentType, APIEndpoint

# 数据模型
from .models import (
    Course,
    Chapter,
    CourseDetail,
    Audiobook,
    AudiobookChapter,
    AudiobookDetail,
    EbookCatalog,
    EbookDetail,
    EbookChapter,
    EbookPage,
    EbookInfo,
)

# 缓存
from .cache import (
    Cache,
    get_cache,
    CachePrefix,
    CacheTTL,
)

# 账户管理
from .account import (
    Account,
    AccountManager,
    get_account_manager,
    get_current_account,
    get_current_cookie,
    get_current_token,
)

# 子模块
from . import course
from . import ebook

# 常用类（便捷导入）
from .course import CourseClient, DedaoClient, CourseDownloader, download_course
from .ebook import EbookClient, EbookDownloader, download_ebook

# 向后兼容
Category = ContentType


__all__ = [
    # 基础类
    "BaseClient",
    "DedaoAPIError",
    "DedaoNetworkError",
    "DedaoAuthError",
    "DedaoAuth",
    "get_cookie_from_chrome",
    "ContentType",
    "Category",
    "APIEndpoint",
    # 数据模型
    "Course",
    "Chapter",
    "CourseDetail",
    "EbookCatalog",
    "EbookDetail",
    "EbookChapter",
    "EbookPage",
    "EbookInfo",
    # 缓存
    "Cache",
    "get_cache",
    "CachePrefix",
    "CacheTTL",
    # 账户管理
    "Account",
    "AccountManager",
    "get_account_manager",
    "get_current_account",
    "get_current_cookie",
    "get_current_token",
    # 子模块
    "course",
    "ebook",
    # 常用类
    "CourseClient",
    "DedaoClient",
    "CourseDownloader",
    "download_course",
    "EbookClient",
    "EbookDownloader",
    "download_ebook",
]
