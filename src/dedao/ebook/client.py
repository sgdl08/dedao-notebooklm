"""电子书 API 客户端。

提供电子书列表、详情和正文分页接口访问。
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from ..base import BaseClient, DedaoAPIError
from ..models import EbookCatalog, EbookDetail, EbookInfo, EbookPage
from ..constants import APIEndpoint, ContentType
from ..cache import get_cache, CachePrefix, CacheTTL
from utils import decrypt_ebook_content

logger = logging.getLogger(__name__)

DEFAULT_PAGE_RENDER_CONFIG = {
    "density": 1,
    "direction": 0,
    "font_name": "pingfang",
    "font_scale": 1,
    "font_size": 16,
    "height": 200000,
    "line_height": "2em",
    "margin_bottom": 20,
    "margin_left": 20,
    "margin_right": 20,
    "margin_top": 0,
    "paragraph_space": "1em",
    "platform": 1,
    "width": 60000,
}


class EbookClient(BaseClient):
    """电子书 API 客户端

    继承自 BaseClient，提供电子书特定的 API 方法。
    """

    def get_ebook_list(
        self,
        page: int = 1,
        page_size: int = 50,
        use_cache: bool = True
    ) -> List[EbookDetail]:
        """获取已购电子书列表

        Args:
            page: 页码
            page_size: 每页数量
            use_cache: 是否使用缓存

        Returns:
            电子书列表
        """
        # 检查缓存
        cache = get_cache()
        cache_key = f"{CachePrefix.EBOOK}list:{page}:{page_size}"
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug("使用缓存的电子书列表")
                return [self._dict_to_ebook_detail(d) for d in cached]

        logger.info(f"获取已购电子书列表 (第 {page} 页)...")

        data = self._request(
            "POST",
            APIEndpoint.EBOOK_LIST if hasattr(APIEndpoint, 'EBOOK_LIST') else "/api/hades/v2/product/list",
            json={
                "page": page,
                "page_size": page_size,
                "category": ContentType.EBOOK,
                "filter": "all",
            },
            headers={"Content-Type": "application/json"}
        )

        ebooks = []
        items = self._get_list(data)

        for item in items:
            ebook = EbookDetail(
                enid=str(item.get("enid") or item.get("id", "")),
                title=item.get("name") or item.get("title", "未知电子书"),
                cover=item.get("logo") or item.get("icon", ""),
                author=item.get("author_name") or item.get("author", ""),
                book_intro=item.get("intro", ""),
                is_vip_book=item.get("is_vip", False),
                extra=item,
            )
            ebooks.append(ebook)

        # 缓存结果
        if use_cache and ebooks:
            cache.set(cache_key, [self._ebook_detail_to_dict(e) for e in ebooks], CacheTTL.COURSE_DETAIL)

        logger.info(f"找到 {len(ebooks)} 本电子书")
        return ebooks

    def get_ebook_detail(self, enid: str, use_cache: bool = True) -> EbookDetail:
        """获取电子书详情

        Args:
            enid: 电子书 ID
            use_cache: 是否使用缓存

        Returns:
            电子书详情
        """
        # 检查缓存
        cache = get_cache()
        cache_key = f"{CachePrefix.EBOOK}detail:{enid}"
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"使用缓存的电子书详情：{enid}")
                return self._dict_to_ebook_detail(cached)

        logger.info(f"获取电子书详情：{enid}")

        data = self._request("GET", f"{APIEndpoint.EBOOK_DETAIL}?id={enid}")
        book_data = self._get_data(data)

        # 解析目录
        catalog = []
        catalog_list = book_data.get("catalog_list", [])
        for item in catalog_list:
            catalog.append(EbookCatalog(
                chapter_id=str(item.get("href") or item.get("chapter_id") or item.get("id", "")),
                title=item.get("text") or item.get("title", ""),
                level=item.get("level", 0),
                order=item.get("playOrder") or item.get("order", 0),
                extra=item,
            ))

        ebook = EbookDetail(
            enid=enid,
            title=book_data.get("operating_title") or book_data.get("title") or "未知电子书",
            cover=book_data.get("cover") or book_data.get("logo", ""),
            author=book_data.get("book_author") or book_data.get("author_name", ""),
            author_info=book_data.get("author_intro", ""),
            book_intro=book_data.get("book_intro") or book_data.get("intro", ""),
            publish_time=book_data.get("publish_time", ""),
            is_vip_book=book_data.get("is_vip", False),
            price=float(book_data.get("price", 0)) if book_data.get("price") else None,
            catalog=catalog,
            extra=book_data,
        )

        # 缓存结果
        if use_cache:
            cache.set(cache_key, self._ebook_detail_to_dict(ebook), CacheTTL.COURSE_DETAIL)

        logger.info(f"电子书包含 {len(catalog)} 个目录项")
        return ebook

    def get_ebook_numeric_id(self, enid: str) -> Optional[int]:
        """获取电子书的数字 ID

        dedao-dl 工具需要数字 ID。

        Args:
            enid: 电子书的字符串 ID

        Returns:
            数字 ID，如果获取失败返回 None
        """
        try:
            detail = self.get_ebook_detail(enid)
            return detail.extra.get("id")
        except Exception:
            return None

    def get_ebook_read_token(self, enid: str) -> str:
        """获取电子书阅读 token。"""
        logger.debug(f"获取电子书阅读令牌：{enid}")

        data = self._request(
            "POST",
            APIEndpoint.EBOOK_READ_TOKEN,
            json={"id": enid},
            headers={"Content-Type": "application/json"},
        )

        token = (self._get_data(data) or {}).get("token", "")
        if not token:
            raise DedaoAPIError("获取阅读令牌失败")
        return token

    def get_ebook_info(self, token: str) -> EbookInfo:
        """获取电子书目录和分页顺序信息。"""
        logger.debug("获取电子书阅读信息...")

        data = self._request("GET", f"{APIEndpoint.EBOOK_INFO}?token={token}")
        payload = self._get_data(data) or {}
        book_info = payload.get("bookInfo", payload)

        toc = [
            EbookCatalog(
                chapter_id=str(item.get("href") or item.get("chapterId") or ""),
                title=item.get("text") or item.get("title", ""),
                level=item.get("level", 0),
                order=item.get("playOrder") or item.get("order", 0),
                extra=item,
            )
            for item in book_info.get("toc", []) or []
        ]

        pages = [
            EbookPage(
                page_id=str(item.get("page_num", "")),
                svg="",
                chapter_id=str(item.get("cid", "")),
            )
            for item in book_info.get("pages", []) or []
        ]

        return EbookInfo(
            token=token,
            toc=toc,
            orders=book_info.get("orders", []) or [],
            pages=pages,
        )

    def get_ebook_pages(
        self,
        chapter_id: str,
        token: str,
        index: int = 0,
        count: int = 20,
        offset: int = 0,
    ) -> Tuple[List[EbookPage], bool]:
        """获取电子书分页内容。"""
        logger.debug(f"获取电子书页面：{chapter_id} index={index}")

        data = self._request(
            "POST",
            APIEndpoint.EBOOK_PAGES,
            json={
                "chapter_id": chapter_id,
                "count": count,
                "index": index,
                "offset": offset,
                "orientation": 0,
                "config": DEFAULT_PAGE_RENDER_CONFIG,
                "token": token,
            },
            headers={"Content-Type": "application/json"},
        )

        payload = self._get_data(data) or {}
        pages = [
            EbookPage(
                page_id=str(page.get("page_id") or page.get("begin_offset") or index),
                svg=page.get("svg", ""),
                chapter_id=chapter_id,
            )
            for page in payload.get("pages", []) or []
        ]
        return pages, payload.get("is_end", True)

    def get_all_chapter_pages(
        self,
        enid: str,
        chapter_id: str,
        token: str,
        use_cache: bool = True,
    ) -> List[str]:
        """获取单个章节全部解密后的 SVG 页面。"""
        cache = get_cache()
        cache_key = f"{CachePrefix.EBOOK_PAGE}{enid}:{chapter_id}"

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"使用缓存的章节页面：{chapter_id}")
                return cached

        index = 0
        count = 20
        svg_contents: List[str] = []

        while True:
            pages, is_end = self.get_ebook_pages(chapter_id, token, index, count)
            for page in pages:
                decrypted_svg = decrypt_ebook_content(page.svg)
                if decrypted_svg:
                    svg_contents.append(decrypted_svg)

            if is_end:
                break

            index += count
            time.sleep(0.05)

        if use_cache and svg_contents:
            cache.set(cache_key, svg_contents, CacheTTL.EBOOK_PAGE)

        return svg_contents

    def resolve_ebook(self, ebook_id_or_title: str) -> EbookDetail:
        """按 enid、数字 ID 或标题解析电子书。"""
        try:
            return self.get_ebook_detail(ebook_id_or_title)
        except Exception:
            pass

        ebooks = self.get_ebook_list()

        for ebook in ebooks:
            if str(ebook.extra.get("id")) == str(ebook_id_or_title):
                return ebook
            if ebook.enid == ebook_id_or_title:
                return ebook
            if ebook.title == ebook_id_or_title:
                return ebook

        keyword = ebook_id_or_title.lower()
        for ebook in ebooks:
            if keyword in ebook.title.lower() or keyword in ebook.author.lower():
                return ebook

        raise DedaoAPIError(f"未找到电子书: {ebook_id_or_title}")

    def search_ebook(self, keyword: str) -> List[EbookDetail]:
        """搜索电子书

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的电子书列表
        """
        ebooks = self.get_ebook_list()
        keyword_lower = keyword.lower()

        return [
            e for e in ebooks
            if keyword_lower in e.title.lower() or keyword_lower in e.author.lower()
        ]

    def _dict_to_ebook_detail(self, data: dict) -> EbookDetail:
        """从字典创建 EbookDetail"""
        catalog = [
            EbookCatalog(
                chapter_id=c.get("chapter_id", ""),
                title=c.get("title", ""),
                level=c.get("level", 0),
                order=c.get("order", 0),
            )
            for c in data.get("catalog", [])
        ]
        return EbookDetail(
            enid=data.get("enid", ""),
            title=data.get("title", ""),
            cover=data.get("cover", ""),
            author=data.get("author", ""),
            author_info=data.get("author_info", ""),
            book_intro=data.get("book_intro", ""),
            publish_time=data.get("publish_time", ""),
            is_vip_book=data.get("is_vip_book", False),
            price=data.get("price"),
            catalog=catalog,
            extra=data.get("extra", {}),
        )

    def _ebook_detail_to_dict(self, ebook: EbookDetail) -> dict:
        """转换 EbookDetail 为字典"""
        return {
            "enid": ebook.enid,
            "title": ebook.title,
            "cover": ebook.cover,
            "author": ebook.author,
            "author_info": ebook.author_info,
            "book_intro": ebook.book_intro,
            "publish_time": ebook.publish_time,
            "is_vip_book": ebook.is_vip_book,
            "price": ebook.price,
            "catalog": [
                {
                    "chapter_id": c.chapter_id,
                    "title": c.title,
                    "level": c.level,
                    "order": c.order,
                }
                for c in ebook.catalog
            ],
            "extra": ebook.extra,
        }
