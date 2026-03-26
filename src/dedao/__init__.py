"""得到 (Dedao) 模块"""

from .models import (
    Course,
    Chapter,
    CourseDetail,
    # Audiobook
    Audiobook,
    AudiobookChapter,
    AudiobookDetail,
    # Ebook
    EbookCatalog,
    EbookDetail,
    EbookChapter,
    EbookPage,
    EbookInfo,
    # Channel
    ChannelPerson,
    ChannelStatistics,
    ChannelInfo,
    ChannelCategory,
    ChannelNote,
    ChannelHomepage,
    # Topic
    Topic,
    TopicNote,
    TopicDetail,
    # Other
    ContentCategory,
    FreeContent,
)
from .auth import DedaoAuth, DedaoQRCodeLogin
from .client import DedaoClient, DedaoAPIError, Category
from .cache import (
    Cache,
    get_cache,
    cache_get,
    cache_set,
    cache_delete,
    CachePrefix,
    CacheTTL,
)
from .account import (
    Account,
    AccountManager,
    get_account_manager,
    get_current_account,
    get_current_cookie,
    get_current_token,
)


# 子模块延迟导入
def get_audiobook_client():
    """获取有声书客户端"""
    from .audiobook import AudiobookClient
    return AudiobookClient


def get_ebook_client():
    """获取电子书客户端"""
    from .ebook import EbookClient
    return EbookClient


def get_channel_client():
    """获取频道客户端"""
    from .channel import ChannelClient
    return ChannelClient


def get_topic_client():
    """获取主题客户端"""
    from .topic import TopicClient
    return TopicClient


__all__ = [
    # Models
    "Course",
    "Chapter",
    "CourseDetail",
    "Audiobook",
    "AudiobookChapter",
    "AudiobookDetail",
    "EbookCatalog",
    "EbookDetail",
    "EbookChapter",
    "EbookPage",
    "EbookInfo",
    "ChannelPerson",
    "ChannelStatistics",
    "ChannelInfo",
    "ChannelCategory",
    "ChannelNote",
    "ChannelHomepage",
    "Topic",
    "TopicNote",
    "TopicDetail",
    "ContentCategory",
    "FreeContent",
    # Auth
    "DedaoAuth",
    "DedaoQRCodeLogin",
    # Client
    "DedaoClient",
    "DedaoAPIError",
    "Category",
    # Cache
    "Cache",
    "get_cache",
    "cache_get",
    "cache_set",
    "cache_delete",
    "CachePrefix",
    "CacheTTL",
    # Account
    "Account",
    "AccountManager",
    "get_account_manager",
    "get_current_account",
    "get_current_cookie",
    "get_current_token",
    # Client getters
    "get_audiobook_client",
    "get_ebook_client",
    "get_channel_client",
    "get_topic_client",
]
