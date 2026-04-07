"""频道/学习圈模块

提供频道信息获取、内容浏览等功能。
"""

import logging
from typing import List, Optional

from .models import (
    ChannelInfo,
    ChannelCategory,
    ChannelNote,
    ChannelHomepage,
    ChannelPerson,
    ChannelStatistics,
)
from .client import DedaoClient, DedaoAPIError
from .cache import get_cache, CachePrefix, CacheTTL

logger = logging.getLogger(__name__)


class ChannelClient(DedaoClient):
    """频道 API 客户端

    继承自 DedaoClient，添加频道特定的 API 方法。
    """

    def get_channel_info(self, channel_id: str) -> ChannelInfo:
        """获取频道信息

        Args:
            channel_id: 频道 ID

        Returns:
            频道信息
        """
        logger.info(f"获取频道信息：{channel_id}")

        # 检查缓存
        cache = get_cache()
        cache_key = f"{CachePrefix.CHANNEL}info:{channel_id}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"使用缓存的频道信息：{channel_id}")
            return self._dict_to_channel_info(cached)

        # POST /sphere/v1/app/channel/info
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/sphere/v1/app/channel/info",
            json={"channel_id": channel_id},
            headers=headers,
        )

        channel_data = data.get("c", {}) or data.get("data", {})

        # 解析频道人物
        host = None
        host_data = channel_data.get("host", {})
        if host_data:
            host = ChannelPerson(
                uid=str(host_data.get("uid", "")),
                name=host_data.get("name", ""),
                avatar=host_data.get("avatar", ""),
                title=host_data.get("title", ""),
            )

        # 解析统计信息
        statistics = None
        stats_data = channel_data.get("statistics", {})
        if stats_data:
            statistics = ChannelStatistics(
                member_count=stats_data.get("member_count", 0),
                note_count=stats_data.get("note_count", 0),
                view_count=stats_data.get("view_count", 0),
            )

        channel = ChannelInfo(
            channel_id=channel_id,
            title=channel_data.get("title") or channel_data.get("name", "未知频道"),
            description=channel_data.get("description") or channel_data.get("intro", ""),
            logo=channel_data.get("logo") or channel_data.get("cover", ""),
            host=host,
            statistics=statistics,
            is_vip=channel_data.get("is_vip", False),
            extra=channel_data,
        )

        # 缓存结果
        cache.set(cache_key, self._channel_info_to_dict(channel), CacheTTL.USER_INFO)

        logger.info(f"频道：{channel.title}")
        return channel

    def get_channel_homepage(self, channel_id: str) -> ChannelHomepage:
        """获取频道首页

        Args:
            channel_id: 频道 ID

        Returns:
            频道首页内容
        """
        logger.info(f"获取频道首页：{channel_id}")

        # POST /pc/sphere/v1/app/topic/homepage/v2
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/pc/sphere/v1/app/topic/homepage/v2",
            json={"channel_id": channel_id},
            headers=headers,
        )

        homepage_data = data.get("c", {}) or data.get("data", {})

        # 频道信息
        channel_data = homepage_data.get("channel", {})
        channel = self.get_channel_info(channel_id) if not channel_data else self._parse_channel_info(channel_data, channel_id)

        # 分类
        categories = []
        for cat_data in homepage_data.get("categories", []):
            categories.append(ChannelCategory(
                id=str(cat_data.get("id", "")),
                name=cat_data.get("name", ""),
                description=cat_data.get("description", ""),
                note_count=cat_data.get("note_count", 0),
            ))

        # 精选笔记
        featured_notes = []
        for note_data in homepage_data.get("featured_notes", []):
            featured_notes.append(self._parse_channel_note(note_data))

        return ChannelHomepage(
            channel=channel,
            categories=categories,
            featured_notes=featured_notes,
        )

    def get_channel_notes(
        self,
        channel_id: str,
        category_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[ChannelNote]:
        """获取频道笔记列表

        Args:
            channel_id: 频道 ID
            category_id: 分类 ID（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            笔记列表
        """
        logger.info(f"获取频道笔记：{channel_id}，分类：{category_id or '全部'}")

        # POST /sphere/v1/app/channel/notes
        headers = {"Content-Type": "application/json"}
        payload = {
            "channel_id": channel_id,
            "page": page,
            "page_size": page_size,
        }
        if category_id:
            payload["category_id"] = category_id

        data = self._request(
            "POST",
            "/sphere/v1/app/channel/notes",
            json=payload,
            headers=headers,
        )

        notes = []
        items = data.get("c", {}).get("list", []) or data.get("list", [])

        for note_data in items:
            notes.append(self._parse_channel_note(note_data))

        logger.info(f"找到 {len(notes)} 条笔记")
        return notes

    def get_channel_vip_info(self, channel_id: str) -> dict:
        """获取频道 VIP 信息

        Args:
            channel_id: 频道 ID

        Returns:
            VIP 信息字典
        """
        logger.info(f"获取频道 VIP 信息：{channel_id}")

        # POST /sphere/v1/app/vip/info?channel_id={id}
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            f"/sphere/v1/app/vip/info?channel_id={channel_id}",
            json={},
            headers=headers,
        )

        return data.get("c", {}) or data.get("data", {})

    def _parse_channel_info(self, data: dict, channel_id: str) -> ChannelInfo:
        """解析频道信息"""
        host = None
        host_data = data.get("host", {})
        if host_data:
            host = ChannelPerson(
                uid=str(host_data.get("uid", "")),
                name=host_data.get("name", ""),
                avatar=host_data.get("avatar", ""),
                title=host_data.get("title", ""),
            )

        statistics = None
        stats_data = data.get("statistics", {})
        if stats_data:
            statistics = ChannelStatistics(
                member_count=stats_data.get("member_count", 0),
                note_count=stats_data.get("note_count", 0),
                view_count=stats_data.get("view_count", 0),
            )

        return ChannelInfo(
            channel_id=channel_id,
            title=data.get("title") or data.get("name", "未知频道"),
            description=data.get("description") or data.get("intro", ""),
            logo=data.get("logo") or data.get("cover", ""),
            host=host,
            statistics=statistics,
            is_vip=data.get("is_vip", False),
            extra=data,
        )

    def _parse_channel_note(self, data: dict) -> ChannelNote:
        """解析频道笔记"""
        author = None
        author_data = data.get("author", {}) or data.get("user", {})
        if author_data:
            author = ChannelPerson(
                uid=str(author_data.get("uid", "")),
                name=author_data.get("name") or author_data.get("nickname", ""),
                avatar=author_data.get("avatar", ""),
                title=author_data.get("title", ""),
            )

        return ChannelNote(
            id=str(data.get("id") or data.get("note_id", "")),
            title=data.get("title", ""),
            content=data.get("content") or data.get("text", ""),
            author=author,
            created_at=data.get("created_at") or data.get("create_time", ""),
            like_count=data.get("like_count", 0),
            comment_count=data.get("comment_count", 0),
            extra=data,
        )

    def _channel_info_to_dict(self, channel: ChannelInfo) -> dict:
        """转换频道信息为字典"""
        return {
            "channel_id": channel.channel_id,
            "title": channel.title,
            "description": channel.description,
            "logo": channel.logo,
            "is_vip": channel.is_vip,
        }

    def _dict_to_channel_info(self, data: dict) -> ChannelInfo:
        """从字典创建频道信息"""
        return ChannelInfo(
            channel_id=data.get("channel_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            logo=data.get("logo", ""),
            is_vip=data.get("is_vip", False),
        )
