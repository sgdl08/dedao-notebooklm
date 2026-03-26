"""主题/社区模块

提供主题列表获取、详情查询和笔记浏览等功能。
"""

import logging
from typing import List, Optional

from .models import Topic, TopicNote, TopicDetail, ChannelPerson
from .client import DedaoClient, DedaoAPIError
from .cache import get_cache, CachePrefix, CacheTTL

logger = logging.getLogger(__name__)


class TopicClient(DedaoClient):
    """主题 API 客户端

    继承自 DedaoClient，添加主题特定的 API 方法。
    """

    def get_topic_list(self, page: int = 1, page_size: int = 20) -> List[Topic]:
        """获取推荐主题列表

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            主题列表
        """
        logger.info(f"获取推荐主题列表 (第 {page} 页)...")

        # POST /pc/ledgers/topic/all
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/pc/ledgers/topic/all",
            json={
                "page": page,
                "page_size": page_size,
            },
            headers=headers,
        )

        topics = []
        items = data.get("c", {}).get("list", []) or data.get("list", [])

        for item in items:
            topics.append(self._parse_topic(item))

        logger.info(f"找到 {len(topics)} 个主题")
        return topics

    def get_topic_detail(self, topic_id: str) -> TopicDetail:
        """获取主题详情

        Args:
            topic_id: 主题 ID

        Returns:
            主题详情
        """
        logger.info(f"获取主题详情：{topic_id}")

        # 检查缓存
        cache = get_cache()
        cache_key = f"{CachePrefix.TOPIC}detail:{topic_id}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"使用缓存的主题详情：{topic_id}")
            return TopicDetail(
                topic=Topic(**cached.get("topic", {})),
                notes=[TopicNote(**n) for n in cached.get("notes", [])],
            )

        # POST /pc/ledgers/topic/detail
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/pc/ledgers/topic/detail",
            json={"topic_id": topic_id},
            headers=headers,
        )

        topic_data = data.get("c", {}) or data.get("data", {})

        # 解析主题
        topic = self._parse_topic(topic_data)

        # 获取笔记列表
        notes = self.get_topic_notes(topic_id)

        detail = TopicDetail(topic=topic, notes=notes)

        # 缓存结果
        cache.set(
            cache_key,
            {
                "topic": {
                    "id": topic.id,
                    "title": topic.title,
                    "description": topic.description,
                    "cover": topic.cover,
                    "note_count": topic.note_count,
                    "participant_count": topic.participant_count,
                    "is_hot": topic.is_hot,
                },
                "notes": [
                    {
                        "id": n.id,
                        "title": n.title,
                        "content": n.content,
                        "created_at": n.created_at,
                        "like_count": n.like_count,
                    }
                    for n in notes
                ],
            },
            CacheTTL.COURSE_DETAIL,
        )

        logger.info(f"主题：{topic.title}，包含 {len(notes)} 条笔记")
        return detail

    def get_topic_notes(
        self,
        topic_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> List[TopicNote]:
        """获取主题笔记列表

        Args:
            topic_id: 主题 ID
            page: 页码
            page_size: 每页数量

        Returns:
            笔记列表
        """
        logger.info(f"获取主题笔记：{topic_id}")

        # POST /pc/ledgers/topic/notes/list
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/pc/ledgers/topic/notes/list",
            json={
                "topic_id": topic_id,
                "page": page,
                "page_size": page_size,
            },
            headers=headers,
        )

        notes = []
        items = data.get("c", {}).get("list", []) or data.get("list", [])

        for item in items:
            notes.append(self._parse_topic_note(item))

        logger.info(f"找到 {len(notes)} 条笔记")
        return notes

    def _parse_topic(self, data: dict) -> Topic:
        """解析主题"""
        return Topic(
            id=str(data.get("id") or data.get("topic_id", "")),
            title=data.get("title") or data.get("name", ""),
            description=data.get("description") or data.get("intro", ""),
            cover=data.get("cover") or data.get("logo", ""),
            note_count=data.get("note_count", 0),
            participant_count=data.get("participant_count", 0),
            is_hot=data.get("is_hot", False),
            extra=data,
        )

    def _parse_topic_note(self, data: dict) -> TopicNote:
        """解析主题笔记"""
        author = None
        author_data = data.get("author", {}) or data.get("user", {})
        if author_data:
            author = ChannelPerson(
                uid=str(author_data.get("uid", "")),
                name=author_data.get("name") or author_data.get("nickname", ""),
                avatar=author_data.get("avatar", ""),
                title=author_data.get("title", ""),
            )

        return TopicNote(
            id=str(data.get("id") or data.get("note_id", "")),
            title=data.get("title", ""),
            content=data.get("content") or data.get("text", ""),
            author=author,
            created_at=data.get("created_at") or data.get("create_time", ""),
            like_count=data.get("like_count", 0),
            comment_count=data.get("comment_count", 0),
            extra=data,
        )
