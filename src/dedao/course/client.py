"""课程 API 客户端

提供课程的列表获取、详情查询等功能。
"""

import logging
from typing import List, Optional

from ..base import BaseClient, DedaoAPIError
from ..models import Course, Chapter, CourseDetail
from ..constants import APIEndpoint, ContentType
from ..cache import get_cache, CachePrefix, CacheTTL

logger = logging.getLogger(__name__)


class CourseClient(BaseClient):
    """课程 API 客户端

    继承自 BaseClient，提供课程特定的 API 方法。
    """

    def get_course_list(
        self,
        category: str = "all",
        page: int = 1,
        page_size: int = 20,
        order: str = "study"
    ) -> dict:
        """获取已购课程/资源列表

        Args:
            category: 分类 (all/bauhinia/odob/ebook/compass)
            page: 页码
            page_size: 每页数量
            order: 排序方式

        Returns:
            包含 list, total, is_more 等字段的字典
        """
        logger.info(f"获取课程列表 (分类={category}, 第 {page} 页)...")

        data = self._request(
            "POST",
            APIEndpoint.COURSE_LIST,
            json={
                "category": category,
                "display_group": True,
                "filter": "all",
                "group_id": 0,
                "order": order,
                "filter_complete": 0,
                "page": page,
                "page_size": page_size,
                "sort_type": "desc",
            },
            headers={"Content-Type": "application/json"}
        )

        resp_data = self._get_data(data)
        items = resp_data.get("list", [])
        total = resp_data.get("total", 0)
        is_more = resp_data.get("is_more", 0)

        courses = []
        for item in items:
            course = Course(
                id=str(item.get("enid") or item.get("id", "")),
                title=item.get("title", "未知课程"),
                cover=item.get("icon", ""),
                author=item.get("author", ""),
                description=item.get("intro", ""),
                chapter_count=item.get("course_num", 0),
                is_finished=item.get("is_finished", 0) == 1,
                category=category if category != "all" else "",
                extra={
                    "product_type": item.get("type", 0),
                    "progress": item.get("progress", 0),
                    "is_group": item.get("is_group", False),
                    "group_id": item.get("group_id", 0),
                },
            )
            courses.append(course)

        logger.info(f"第 {page} 页找到 {len(courses)} 个课程")

        return {
            "list": courses,
            "total": total,
            "is_more": is_more,
            "page": page,
            "page_size": page_size,
        }

    def get_course_list_all(self, category: str = "all") -> List[Course]:
        """获取所有已购课程（自动分页）"""
        all_courses = []
        page = 1

        while True:
            result = self.get_course_list(category=category, page=page)
            courses = result.get("list", [])
            total = result.get("total", 0)
            is_more = result.get("is_more", 0)

            all_courses.extend(courses)

            if not is_more or len(all_courses) >= total:
                break

            page += 1

        logger.info(f"共获取 {len(all_courses)} 个课程")
        return all_courses

    def get_course_detail(self, course_id: str) -> CourseDetail:
        """获取课程详情"""
        logger.info(f"获取课程详情：{course_id}")

        data = self._request(
            "POST",
            APIEndpoint.COURSE_DETAIL,
            json={"detail_id": course_id, "is_login": 1},
            headers={"Content-Type": "application/json"}
        )

        course_data = self._get_data(data)
        class_info = course_data.get("class_info", {})

        course = Course(
            id=str(class_info.get("enid") or course_id),
            title=class_info.get("name", "未知课程"),
            cover=class_info.get("logo", ""),
            author=class_info.get("lecturer_name", ""),
            description=class_info.get("intro", ""),
            chapter_count=class_info.get("formal_article_count", 0),
        )

        # 获取所有文章
        chapters = self._get_all_articles(course_id)

        return CourseDetail(course=course, chapters=chapters)

    def _get_all_articles(self, course_id: str) -> List[Chapter]:
        """获取课程所有文章"""
        all_articles = []
        max_order_num = 0

        while True:
            articles = self._get_article_list(course_id, max_order_num=max_order_num, reverse=True)
            if not articles:
                break

            all_articles.extend(articles)

            min_order = min(a.get("order_num", 0) for a in articles)
            if min_order <= 1:
                break

            max_order_num = min_order - 1

            if len(articles) < 30:
                break

        all_articles.sort(key=lambda x: x.get("order_num", 0))

        chapters = []
        for article in all_articles:
            audio_info = article.get("audio", {})
            chapter = Chapter(
                id=str(article.get("enid") or article.get("id", "")),
                course_id=course_id,
                title=article.get("title", "未知文章"),
                sort_order=article.get("order_num", 0),
                audio_url=audio_info.get("mp3_play_url", "") if audio_info else "",
                audio_duration=audio_info.get("duration", 0) if audio_info else None,
                content=article.get("summary", ""),
                extra={"audio": audio_info},
            )
            chapters.append(chapter)

        logger.info(f"课程包含 {len(chapters)} 个章节")
        return chapters

    def _get_article_list(
        self,
        course_id: str,
        chapter_id: str = "",
        max_id: int = 0,
        max_order_num: int = 0,
        reverse: bool = False
    ) -> list:
        """获取课程文章列表"""
        data = self._request(
            "POST",
            APIEndpoint.ARTICLE_LIST,
            json={
                "chapter_id": chapter_id,
                "count": 30,
                "detail_id": course_id,
                "include_edge": False,
                "is_unlearn": False,
                "max_id": max_id,
                "max_order_num": max_order_num,
                "reverse": reverse,
                "since_id": 0,
                "since_order_num": 0,
                "unlearn_switch": False,
            },
            headers={"Content-Type": "application/json"}
        )

        resp_data = self._get_data(data)
        return resp_data.get("article_list", [])

    def get_chapter_content(self, chapter_id: str) -> Chapter:
        """获取章节详细内容"""
        logger.info(f"获取章节内容：{chapter_id}")

        # 获取文章 token
        token_data = self._request(
            "POST",
            APIEndpoint.ARTICLE_INFO,
            json={"detail_id": chapter_id},
            headers={"Content-Type": "application/json"}
        )

        token_info = self._get_data(token_data)
        token = token_info.get("dd_article_token", "") or token_info.get("token", "")

        if not token:
            raise DedaoAPIError(f"章节 token 为空：{chapter_id}")

        # 获取文章内容
        article_data = self._request(
            "GET",
            APIEndpoint.ARTICLE_CONTENT,
            params={"token": token, "appid": "1632426125495894021", "is_new": "1"}
        )

        article_info = self._get_data(article_data)
        content = (
            article_info.get("content") or
            article_info.get("text") or
            article_info.get("body") or
            ""
        )

        article_meta = token_info.get("article_info", {})

        return Chapter(
            id=str(article_info.get("id") or chapter_id),
            course_id=str(article_info.get("class_id", "")),
            title=article_meta.get("title") or article_info.get("title", "未知章节"),
            content=content,
        )


# 向后兼容别名
DedaoClient = CourseClient
