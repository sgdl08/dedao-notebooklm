"""得到 (Dedao) API 客户端"""

import logging
import json
from typing import List, Optional
from pathlib import Path

import requests

from .auth import DedaoAuth
from .models import Course, Chapter, CourseDetail
from .cache import get_cache, CachePrefix, CacheTTL

logger = logging.getLogger(__name__)

# 得到 API 端点
DEDIAO_API_BASE = "https://www.dedao.cn"

# 课程分类常量
class Category:
    """课程分类常量"""
    ALL = "all"          # 全部
    COURSE = "bauhinia"  # 课程
    AUDIOBOOK = "odob"   # 有声书/每天听本书
    EBOOK = "ebook"      # 电子书
    ACE = "compass"      # 锦囊


class DedaoAPIError(Exception):
    """得到 API 错误"""
    pass


class DedaoClient:
    """得到 API 客户端

    提供课程列表获取、章节内容下载等功能。
    """

    def __init__(self, cookie: Optional[str] = None, debug: bool = False):
        """初始化客户端

        Args:
            cookie: 得到网站的登录 Cookie
            debug: 是否开启调试模式（打印原始 API 返回）
        """
        self._auth = DedaoAuth(cookie)
        self._session = requests.Session()
        self._session.headers.update(self._auth.headers)
        self._debug = debug

    def set_cookie(self, cookie: str):
        """设置 Cookie"""
        self._auth.cookie = cookie
        self._session.headers.update(self._auth.headers)

    def _request(self, method: str, url: str, **kwargs) -> dict:
        """发送 HTTP 请求

        Args:
            method: HTTP 方法
            url: 请求 URL
            **kwargs: 传递给 requests 的其他参数

        Returns:
            API 响应数据

        Raises:
            DedaoAPIError: 请求失败时
        """
        if not url.startswith(("http://", "https://")):
            url = f"{DEDIAO_API_BASE}{url}"

        try:
            response = self._session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()

            data = response.json()

            # 调试模式：打印原始返回
            if self._debug:
                logger.debug(f"API 响应 ({url}):")
                logger.debug(json.dumps(data, indent=2, ensure_ascii=False))

            # 检查业务错误
            if data.get("code") not in (0, 200, None):
                error_msg = data.get("msg") or data.get("message") or "未知错误"
                raise DedaoAPIError(f"API 错误：{error_msg} (code={data.get('code')})")

            return data

        except requests.exceptions.Timeout:
            raise DedaoAPIError("请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            raise DedaoAPIError("连接失败，请检查网络或得到网站是否可访问")
        except requests.exceptions.HTTPError as e:
            raise DedaoAPIError(f"HTTP 错误：{e.response.status_code}")
        except ValueError as e:
            raise DedaoAPIError(f"解析响应失败：{e}")

    def get_course_categories(self) -> List[dict]:
        """获取课程分类列表（包含数量统计）

        Returns:
            分类列表，每个元素包含 name, count, category 等字段
        """
        logger.info("获取课程分类列表...")

        headers = {"Content-Type": "application/json"}
        data = self._request("POST", "/api/hades/v1/index/detail", headers=headers)

        categories = []
        # Response structure: {h: {...}, c: {data: {list: [...]}}}
        category_list = (
            data.get("c", {}).get("data", {}).get("list", [])
            or data.get("c", {}).get("list", [])
            or data.get("data", {}).get("list", [])
        )

        for item in category_list:
            categories.append({
                "name": item.get("name", ""),
                "count": item.get("count", 0),
                "category": item.get("category", ""),
            })

        logger.info(f"找到 {len(categories)} 个分类")
        return categories

    def get_course_list(
        self,
        category: str = "all",
        page: int = 1,
        page_size: int = 20,
        order: str = "study",
    ) -> dict:
        """获取已购课程/资源列表（支持分页和分类筛选）

        Args:
            category: 分类，可选值：
                - "all": 全部
                - "bauhinia": 课程
                - "odob": 有声书/每天听本书
                - "ebook": 电子书
                - "compass": 锦囊
            page: 页码（从 1 开始）
            page_size: 每页数量
            order: 排序方式，"study" 按学习进度

        Returns:
            包含 list, total, is_more 等字段的字典
        """
        logger.info(f"获取课程列表 (分类={category}, 第 {page} 页)...")

        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/api/hades/v2/product/list",
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
            headers=headers,
        )

        # 解析响应
        resp_data = data.get("c", {}) or data.get("data", {})
        items = resp_data.get("list", [])
        total = resp_data.get("total", 0)
        is_more = resp_data.get("is_more", 0)

        courses = []
        for item in items:
            # 判断是否为分组
            is_group = item.get("is_group", False)

            course = Course(
                id=str(item.get("enid") or item.get("id", "")),
                title=item.get("title", "未知课程"),
                cover=item.get("icon", ""),
                author=item.get("author", ""),
                description=item.get("intro", ""),
                chapter_count=item.get("course_num", 0),
                is_finished=item.get("is_finished", 0) == 1,
                category=category if category != "all" else "",
                # 保存额外信息
                extra={
                    "product_type": item.get("type", 0),
                    "class_type": item.get("class_type", 0),
                    "class_id": item.get("class_id", 0),
                    "progress": item.get("progress", 0),
                    "create_time": item.get("create_time", 0),
                    "price": item.get("price", ""),
                    "duration": item.get("duration", 0),
                    "is_group": is_group,
                    "group_id": item.get("group_id", 0),
                    "log_type": item.get("log_type", ""),
                },
            )
            courses.append(course)

        logger.info(f"第 {page} 页找到 {len(courses)} 个课程，总计 {total} 个")

        return {
            "list": courses,
            "total": total,
            "is_more": is_more,
            "page": page,
            "page_size": page_size,
        }

    def get_course_list_all(self, category: str = "all", order: str = "study") -> List[Course]:
        """获取所有已购课程（自动处理分页）

        Args:
            category: 分类（同 get_course_list）
            order: 排序方式

        Returns:
            所有课程列表
        """
        logger.info(f"获取所有课程 (分类={category})...")

        all_courses = []
        page = 1
        page_size = 20

        while True:
            result = self.get_course_list(category=category, page=page, page_size=page_size, order=order)
            courses = result.get("list", [])
            total = result.get("total", 0)
            is_more = result.get("is_more", 0)

            all_courses.extend(courses)

            # 检查是否还有更多
            if not is_more or len(all_courses) >= total:
                break

            page += 1

        logger.info(f"共获取 {len(all_courses)} 个课程")
        return all_courses

    def get_course_group_list(
        self,
        category: str,
        group_id: int,
        page: int = 1,
        page_size: int = 20,
        order: str = "study",
    ) -> dict:
        """获取分组内的课程列表

        Args:
            category: 分类
            group_id: 分组 ID
            page: 页码
            page_size: 每页数量
            order: 排序方式

        Returns:
            包含 list, total, is_more 等字段的字典
        """
        logger.info(f"获取分组课程 (group_id={group_id}, 第 {page} 页)...")

        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/api/hades/v2/product/group/list",
            json={
                "category": category,
                "display_group": False,  # 不嵌套分组
                "filter": "group",
                "group_id": group_id,
                "order": order,
                "filter_complete": 0,
                "page": page,
                "page_size": page_size,
                "sort_type": "desc",
            },
            headers=headers,
        )

        # 解析响应
        resp_data = data.get("c", {}) or data.get("data", {})
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
                category=category,
                extra={
                    "product_type": item.get("type", 0),
                    "class_type": item.get("class_type", 0),
                    "class_id": item.get("class_id", 0),
                    "progress": item.get("progress", 0),
                    "create_time": item.get("create_time", 0),
                    "price": item.get("price", ""),
                    "duration": item.get("duration", 0),
                    "log_type": item.get("log_type", ""),
                },
            )
            courses.append(course)

        return {
            "list": courses,
            "total": total,
            "is_more": is_more,
            "page": page,
            "page_size": page_size,
        }

    def get_article_list(self, course_id: str, chapter_id: str = "", max_id: int = 0,
                         max_order_num: int = 0, reverse: bool = False) -> List[dict]:
        """获取课程文章列表（使用 purchase/article_list API）

        Args:
            course_id: 课程 ID (enid)
            chapter_id: 章节ID，为空则获取所有文章
            max_id: 分页参数，用于获取更多文章
            max_order_num: 按序号分页参数（配合 reverse=True 使用）
            reverse: 是否倒序获取（True 时从最新开始）

        Returns:
            文章列表
        """
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/api/pc/bauhinia/pc/class/purchase/article_list",
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
            headers=headers,
        )

        # 解析响应 - API 返回 article_list 字段
        resp_data = data.get("c", {}) or data.get("data", {})
        return resp_data.get("article_list", [])

    def get_all_articles(self, course_id: str) -> List[dict]:
        """获取课程所有文章（自动处理分页）

        使用 reverse=True 和 max_order_num 进行分页，确保获取全部文章。

        Args:
            course_id: 课程 ID (enid)

        Returns:
            所有文章列表（按 order_num 升序排列）
        """
        all_articles = []
        seen_ids = set()
        seen_orders = set()
        max_order_num = 0
        page = 1

        while True:
            # 使用 reverse=True 从最新开始获取，然后用 max_order_num 向前翻页
            articles = self.get_article_list(
                course_id,
                chapter_id="",
                max_order_num=max_order_num,
                reverse=True
            )
            if not articles:
                break

            for article in articles:
                aid = str(article.get("enid") or article.get("id") or "")
                order = article.get("order_num", 0)
                # 分页边界可能重叠，按 id/order 去重
                key = aid or f"order:{order}"
                if key in seen_ids or order in seen_orders:
                    continue
                seen_ids.add(key)
                seen_orders.add(order)
                all_articles.append(article)
            logger.debug(f"第 {page} 页获取 {len(articles)} 篇文章，累计 {len(all_articles)} 篇")

            # 获取当前批次中最小的 order_num 作为下一页的 max_order_num
            # reverse=True 时，返回的列表是按 order_num 降序的
            min_order = min(a.get("order_num", 0) for a in articles)
            if min_order <= 1:  # 已经到达最早的文章
                break

            # 注意：该接口为“严格小于 max_order_num”，不能减 1，否则会跳过边界项
            max_order_num = min_order
            page += 1

            # 如果返回少于 30 条，说明没有更多了
            if len(articles) < 30:
                break

        # 按 order_num 升序排列
        all_articles.sort(key=lambda x: x.get("order_num", 0))
        logger.info(f"获取到 {len(all_articles)} 篇文章")
        return all_articles

    def get_course_detail(self, course_id: str) -> CourseDetail:
        """获取课程详情（包含章节列表）

        Args:
            course_id: 课程 ID (enid)

        Returns:
            课程详情
        """
        logger.info(f"获取课程详情：{course_id}")

        cache = get_cache()
        cache_key = f"{CachePrefix.COURSE}detail:{course_id}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"命中课程详情缓存：{course_id}")
            return self._dict_to_course_detail(cached)

        # 使用新的 API 端点获取课程信息
        # POST /pc/bauhinia/pc/class/info {"detail_id": course_id, "is_login": 1}
        headers = {"Content-Type": "application/json"}
        data = self._request("POST", "/pc/bauhinia/pc/class/info", json={"detail_id": course_id, "is_login": 1}, headers=headers)

        # 检查响应
        if data.get("h", {}).get("c") != 0:
            error_msg = data.get("h", {}).get("e", "未知错误")
            raise DedaoAPIError(f"获取课程详情失败：{error_msg}")

        course_data = data.get("c", {})

        # 提取课程信息
        class_info = course_data.get("class_info", {})

        course = Course(
            id=str(class_info.get("enid") or course_id),
            title=class_info.get("name", "未知课程"),
            cover=class_info.get("logo", ""),
            author=class_info.get("lecturer_name", ""),
            description=class_info.get("intro", ""),
            chapter_count=class_info.get("formal_article_count", 0),
            is_finished=class_info.get("is_finished", False),
        )

        # 优先使用 purchase/article_list API 获取所有文章
        # 这个 API 会返回完整的文章列表，不受 chapter_list 限制
        chapters = []

        try:
            all_articles = self.get_all_articles(course_id)
            if all_articles:
                for article in all_articles:
                    article_id = article.get("enid") or article.get("id") or ""
                    audio_info = article.get("audio", {})

                    chapter = Chapter(
                        id=str(article_id),
                        course_id=course_id,
                        title=article.get("title", "未知文章"),
                        sort_order=article.get("order_num", 0),
                        audio_url=audio_info.get("mp3_play_url", "") if audio_info else "",
                        audio_duration=audio_info.get("duration", 0) if audio_info else None,
                        content=article.get("summary", ""),
                        is_free=article.get("is_free_try", False),
                        extra={"audio": audio_info if audio_info else None},
                    )
                    chapters.append(chapter)

                # 交叉补齐：某些课程 article_list 与 chapter_list 不一致时，补上缺失项
                existing_ids = {str(ch.id) for ch in chapters if ch.id}
                for chapter_info in course_data.get("chapter_list", []):
                    for article in chapter_info.get("article_list", []):
                        article_id = str(article.get("enid") or article.get("id") or article.get("article_id") or "")
                        if not article_id or article_id in existing_ids:
                            continue
                        audio_info = article.get("audio", {})
                        chapters.append(
                            Chapter(
                                id=article_id,
                                course_id=course_id,
                                title=article.get("title", "未知文章"),
                                sort_order=article.get("order_num", 0),
                                audio_url=audio_info.get("mp3_play_url", "") if audio_info else "",
                                audio_duration=audio_info.get("duration", 0) if audio_info else None,
                                content=article.get("summary", ""),
                                is_free=article.get("is_free_try", False),
                                extra={
                                    "audio": audio_info if audio_info else None,
                                    "chapter_name": chapter_info.get("name", ""),
                                    "source": "chapter_list_fallback",
                                },
                            )
                        )
                        existing_ids.add(article_id)

                chapters.sort(key=lambda x: x.sort_order)
                logger.info(f"课程包含 {len(chapters)} 个章节（从 article_list API 获取）")
                detail = CourseDetail(course=course, chapters=chapters)
                cache.set(cache_key, self._course_detail_to_dict(detail), CacheTTL.COURSE_DETAIL)
                return detail
        except Exception as e:
            logger.warning(f"从 article_list API 获取失败，尝试其他方式: {e}")

        # 备选方案：从 chapter_list 中提取
        chapter_list = course_data.get("chapter_list", [])

        for chapter_info in chapter_list:
            # 获取章节内的文章列表
            article_list = chapter_info.get("article_list", [])
            for article in article_list:
                # 兼容多种字段名
                article_id = article.get("enid") or article.get("id") or article.get("article_id") or ""

                # 获取音频信息
                audio_info = article.get("audio", {})
                audio_url = ""
                audio_duration = None

                if audio_info:
                    audio_url = audio_info.get("mp3_play_url", "")
                    audio_duration = audio_info.get("duration", 0)

                chapter = Chapter(
                    id=str(article_id),
                    course_id=course_id,
                    title=article.get("title", "未知文章"),
                    sort_order=article.get("order_num", 0),
                    audio_url=audio_url,
                    audio_duration=audio_duration,
                    content=article.get("summary", ""),
                    is_free=article.get("is_free_try", False),
                    extra={
                        "audio": audio_info if audio_info else None,
                        "chapter_name": chapter_info.get("name", ""),
                    },
                )
                chapters.append(chapter)

        # 如果没有从 chapter_list 中找到文章，尝试其他结构
        if not chapters:
            # 尝试 flat_article_list
            flat_articles = course_data.get("flat_article_list", [])
            for idx, article in enumerate(flat_articles):
                article_id = article.get("enid") or article.get("id") or ""
                audio_info = article.get("audio", {})
                chapters.append(Chapter(
                    id=str(article_id),
                    course_id=course_id,
                    title=article.get("title", f"第{idx + 1}章"),
                    sort_order=article.get("order_num", idx),
                    audio_url=audio_info.get("mp3_play_url", "") if audio_info else "",
                    audio_duration=audio_info.get("duration", 0) if audio_info else None,
                    content=article.get("summary", ""),
                    is_free=article.get("is_free_try", False),
                    extra={"audio": audio_info if audio_info else None},
                ))

        logger.info(f"课程包含 {len(chapters)} 个章节")
        detail = CourseDetail(course=course, chapters=chapters)
        cache.set(cache_key, self._course_detail_to_dict(detail), CacheTTL.COURSE_DETAIL)
        return detail

    def get_chapter_content(self, chapter_id: str) -> Chapter:
        """获取章节详细内容

        Args:
            chapter_id: 章节 ID (article enid)

        Returns:
            包含详细内容的章节对象
        """
        logger.info(f"获取章节内容：{chapter_id}")

        cache = get_cache()
        cache_key = f"{CachePrefix.CHAPTER}content:{chapter_id}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"命中章节缓存：{chapter_id}")
            return self._dict_to_chapter(cached)

        # 第一步：获取文章 token
        # POST /pc/bauhinia/pc/article/info {"detail_id": chapter_id}
        headers = {"Content-Type": "application/json"}
        try:
            token_data = self._request(
                "POST",
                "/pc/bauhinia/pc/article/info",
                json={"detail_id": chapter_id},
                headers=headers,
            )
        except DedaoAPIError:
            raise DedaoAPIError(f"无法获取章节 token：{chapter_id}")

        # 解析 token 信息
        token_info = token_data.get("c", {}) or token_data.get("data", {})
        token = token_info.get("dd_article_token", "") or token_info.get("token", "")
        app_id = "1632426125495894021"

        # 从 article_info 中提取标题和排序信息
        article_meta = token_info.get("article_info", {})
        chapter_title = article_meta.get("title", "")
        chapter_order = article_meta.get("chapter_id", 0)

        if not token:
            raise DedaoAPIError(f"章节 token 为空：{chapter_id}")

        # 第二步：使用 token 获取文章详情
        # GET /pc/ddarticle/v1/article/get/v2?token=xxx&appid=xxx&is_new=1
        try:
            article_data = self._request(
                "GET",
                "/pc/ddarticle/v1/article/get/v2",
                params={"token": token, "appid": app_id, "is_new": "1"},
            )
        except DedaoAPIError:
            raise DedaoAPIError(f"无法获取章节详情：{chapter_id}")

        # 解析文章内容
        article_info = (
            article_data.get("c", {}) or
            article_data.get("data", {}) or
            {}
        )

        # 提取内容（可能是 HTML 或 Markdown）
        content = (
            article_info.get("content") or
            article_info.get("text") or
            article_info.get("body") or
            article_info.get("summary") or
            ""
        )

        chapter = Chapter(
            id=str(article_info.get("id") or chapter_id),
            course_id=str(article_info.get("class_id", "")),
            title=chapter_title or article_info.get("title", "未知章节"),
            sort_order=chapter_order or article_info.get("order_num", 0),
            content=content,
            audio_url=(
                article_info.get("audio_url") or
                (article_info.get("audio", {}).get("mp3_play_url", "") if isinstance(article_info.get("audio"), dict) else "") or
                article_info.get("voice_url") or
                ""
            ),
            audio_duration=article_info.get("audio_duration") or (article_info.get("audio", {}).get("duration", 0) if isinstance(article_info.get("audio"), dict) else 0),
        )

        cache.set(cache_key, self._chapter_to_dict(chapter), CacheTTL.COURSE_DETAIL)
        return chapter


    def download_file(self, url: str, save_path: Path) -> Path:
        """下载文件

        Args:
            url: 文件 URL
            save_path: 保存路径

        Returns:
            保存的文件路径
        """
        logger.info(f"下载文件：{url} -> {save_path}")

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with self._session.get(url, stream=True) as response:
            response.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        logger.info(f"文件已下载到 {save_path}")
        return save_path

    def save_config(self, cookie: Optional[str] = None):
        """保存 Cookie 配置"""
        self._auth.save_config(cookie)

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self._auth.is_authenticated()

    # ==================== 兼容/辅助方法 ====================

    def get_all_courses(self, category: str = "all", order: str = "study") -> List[Course]:
        """兼容旧接口：获取全部课程。"""
        return self.get_course_list_all(category=category, order=order)

    def get_user_info(self) -> dict:
        """兼容旧接口：获取用户信息。

        得到站点接口经常变动，这里优先返回可用的账户态信息。
        """
        try:
            # 尝试一个轻量请求验证登录态。
            result = self.get_course_list(page=1, page_size=1)
            return {
                "nick_name": "dedao_user",
                "authenticated": True,
                "course_total": result.get("total", 0),
            }
        except Exception as e:
            raise DedaoAPIError(f"获取用户信息失败：{e}")

    # ==================== 缓存序列化辅助 ====================

    def _chapter_to_dict(self, chapter: Chapter) -> dict:
        return {
            "id": chapter.id,
            "course_id": chapter.course_id,
            "title": chapter.title,
            "sort_order": chapter.sort_order,
            "content": chapter.content,
            "audio_url": chapter.audio_url,
            "audio_duration": chapter.audio_duration,
            "downloaded": chapter.downloaded,
            "local_path": chapter.local_path,
            "is_free": chapter.is_free,
            "extra": chapter.extra,
        }

    def _dict_to_chapter(self, data: dict) -> Chapter:
        return Chapter(
            id=str(data.get("id", "")),
            course_id=str(data.get("course_id", "")),
            title=data.get("title", "未知章节"),
            sort_order=data.get("sort_order", 0),
            content=data.get("content", ""),
            audio_url=data.get("audio_url"),
            audio_duration=data.get("audio_duration"),
            downloaded=data.get("downloaded", False),
            local_path=data.get("local_path"),
            is_free=data.get("is_free", False),
            extra=data.get("extra", {}),
        )

    def _course_detail_to_dict(self, detail: CourseDetail) -> dict:
        return {
            "course": {
                "id": detail.course.id,
                "title": detail.course.title,
                "cover": detail.course.cover,
                "author": detail.course.author,
                "description": detail.course.description,
                "chapter_count": detail.course.chapter_count,
                "is_finished": detail.course.is_finished,
                "category": detail.course.category,
                "extra": detail.course.extra,
            },
            "chapters": [self._chapter_to_dict(ch) for ch in detail.chapters],
        }

    def _dict_to_course_detail(self, data: dict) -> CourseDetail:
        course_data = data.get("course", {})
        course = Course(
            id=str(course_data.get("id", "")),
            title=course_data.get("title", "未知课程"),
            cover=course_data.get("cover", ""),
            author=course_data.get("author", ""),
            description=course_data.get("description", ""),
            chapter_count=course_data.get("chapter_count", 0),
            is_finished=course_data.get("is_finished", False),
            category=course_data.get("category", ""),
            extra=course_data.get("extra", {}),
        )
        chapters = [self._dict_to_chapter(item) for item in data.get("chapters", [])]
        return CourseDetail(course=course, chapters=chapters)
