"""有声书下载模块

提供有声书的列表获取、详情查询和下载功能。
"""

import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

import requests

from .models import Audiobook, AudiobookChapter, AudiobookDetail
from .base import DedaoAPIError
from .course.client import CourseClient as DedaoClient  # 使用课程客户端作为基类
from .cache import get_cache, CachePrefix, CacheTTL

logger = logging.getLogger(__name__)


class AudiobookClient(DedaoClient):
    """有声书 API 客户端

    继承自 DedaoClient，添加有声书特定的 API 方法。
    """

    def get_audiobook_list(
        self,
        page: int = 1,
        page_size: int = 20,
        order: str = "study",
        expand_groups: bool = True,
    ) -> dict:
        """获取已购有声书列表（支持分页）

        Args:
            page: 页码
            page_size: 每页数量
            order: 排序方式
            expand_groups: 是否自动展开分组

        Returns:
            包含 list, total, is_more 等字段的字典
        """
        logger.info(f"获取已购有声书列表 (第 {page} 页)...")

        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/api/hades/v2/product/list",
            json={
                "category": "odob",  # 有声书类型
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

        audiobooks = []
        for item in items:
            # 检查是否为名家讲书合集
            is_group = item.get("is_group", False)
            odob_ext = item.get("odob_group_ext_info", {})

            audiobook = Audiobook(
                alias_id=str(item.get("enid") or item.get("id", "")),
                title=item.get("title", "未知有声书"),
                cover=item.get("icon", ""),
                author=item.get("author", ""),
                reader="",
                duration=odob_ext.get("odob_total_duration", 0) or item.get("duration", 0),
                summary=item.get("intro", ""),
                is_vip=item.get("is_vip", False),
                extra={
                    "is_group": is_group,
                    "group_id": item.get("group_id", 0),
                    "group_type": odob_ext.get("group_type", 0),
                    "progress": item.get("progress", 0),
                    "type": item.get("type", 0),
                    "log_type": item.get("log_type", ""),
                    "audio_detail": odob_ext.get("audio_detail", {}),
                },
            )
            audiobooks.append(audiobook)

        logger.info(f"第 {page} 页找到 {len(audiobooks)} 本有声书，总计 {total} 本")

        return {
            "list": audiobooks,
            "total": total,
            "is_more": is_more,
            "page": page,
            "page_size": page_size,
        }

    def get_audiobook_list_all(self, order: str = "study", expand_groups: bool = False) -> List[Audiobook]:
        """获取所有已购有声书（自动处理分页）

        Args:
            order: 排序方式
            expand_groups: 是否自动展开分组

        Returns:
            所有有声书列表
        """
        logger.info("获取所有有声书...")

        all_audiobooks = []
        page = 1
        page_size = 20

        while True:
            result = self.get_audiobook_list(page=page, page_size=page_size, order=order)
            audiobooks = result.get("list", [])
            total = result.get("total", 0)
            is_more = result.get("is_more", 0)

            all_audiobooks.extend(audiobooks)

            if not is_more or len(all_audiobooks) >= total:
                break

            page += 1

        logger.info(f"共获取 {len(all_audiobooks)} 本有声书")
        return all_audiobooks

    def get_audiobook_detail(self, alias_id: str) -> AudiobookDetail:
        """获取有声书详情

        Args:
            alias_id: 有声书别名 ID

        Returns:
            有声书详情
        """
        logger.info(f"获取有声书详情：{alias_id}")

        # 检查缓存
        cache = get_cache()
        cache_key = f"{CachePrefix.AUDIOBOOK}detail:{alias_id}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"使用缓存的有声书详情：{alias_id}")
            return AudiobookDetail(
                audiobook=Audiobook(**cached.get("audiobook", {})),
                chapters=[AudiobookChapter(**ch) for ch in cached.get("chapters", [])],
            )

        # POST /pc/odob/pc/audio/detail/alias
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/pc/odob/pc/audio/detail/alias",
            json={"alias_id": alias_id},
            headers=headers,
        )

        # 解析响应
        audio_data = data.get("c", {}) or data.get("data", {})

        # 有声书基本信息
        audiobook = Audiobook(
            alias_id=alias_id,
            title=audio_data.get("title") or audio_data.get("name", "未知有声书"),
            cover=audio_data.get("cover") or audio_data.get("logo", ""),
            author=audio_data.get("author") or audio_data.get("lecturer_name", ""),
            reader=audio_data.get("reader_name", ""),
            duration=audio_data.get("duration", 0),
            mp3_url=audio_data.get("mp3_play_url") or audio_data.get("audio_url", ""),
            summary=audio_data.get("intro") or audio_data.get("summary", ""),
            is_vip=audio_data.get("is_vip", False),
            extra=audio_data,
        )

        # 章节列表
        chapters = []
        chapter_list = audio_data.get("chapters", []) or audio_data.get("articles", [])

        for idx, chapter_info in enumerate(chapter_list):
            chapter = AudiobookChapter(
                id=str(chapter_info.get("enid") or chapter_info.get("id", "")),
                title=chapter_info.get("title", f"第{idx + 1}章"),
                sort_order=chapter_info.get("order_num", idx),
                audio_url=chapter_info.get("mp3_play_url") or chapter_info.get("audio_url", ""),
                duration=chapter_info.get("duration", 0),
                content=chapter_info.get("content") or chapter_info.get("text", ""),
                extra=chapter_info,
            )
            chapters.append(chapter)

        detail = AudiobookDetail(audiobook=audiobook, chapters=chapters)

        # 缓存结果
        cache.set(
            cache_key,
            {
                "audiobook": audiobook.__dict__,
                "chapters": [ch.__dict__ for ch in chapters],
            },
            CacheTTL.COURSE_DETAIL,
        )

        logger.info(f"有声书包含 {len(chapters)} 个章节")
        return detail

    def get_audiobook_collection(self, enid: str) -> List[Audiobook]:
        """获取有声书合集

        Args:
            enid: 合集 ID

        Returns:
            合集中的有声书列表
        """
        logger.info(f"获取有声书合集：{enid}")

        # POST /pc/sunflower/v1/depot/vip-user/topic-pkg/odob/details
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/pc/sunflower/v1/depot/vip-user/topic-pkg/odob/details",
            json={"enid": enid},
            headers=headers,
        )

        audiobooks = []
        items = data.get("c", {}).get("list", []) or data.get("list", [])

        for item in items:
            audiobook = Audiobook(
                alias_id=str(item.get("enid") or item.get("alias_id", "")),
                title=item.get("name") or item.get("title", "未知有声书"),
                cover=item.get("logo") or item.get("cover", ""),
                author=item.get("lecturer_name") or item.get("author", ""),
                reader=item.get("reader_name", ""),
                duration=item.get("duration", 0),
                mp3_url=item.get("mp3_play_url", ""),
                summary=item.get("intro", ""),
                is_vip=item.get("is_vip", False),
                extra=item,
            )
            audiobooks.append(audiobook)

        logger.info(f"合集包含 {len(audiobooks)} 本有声书")
        return audiobooks


@dataclass
class AudiobookDownloadResult:
    """有声书下载结果"""
    audiobook: Audiobook
    output_dir: Path
    downloaded_files: List[Path]
    failed_chapters: List[str]
    total_size: int = 0  # 字节


class AudiobookDownloader:
    """有声书下载器

    功能：
    - 下载有声书音频文件 (MP3)
    - 生成文字内容 (Markdown)
    - 生成 PDF（可选）
    """

    def __init__(self, client: Optional[AudiobookClient] = None):
        """初始化下载器

        Args:
            client: 有声书客户端
        """
        self.client = client or AudiobookClient()
        self._session = requests.Session()

    def download(
        self,
        alias_id: str,
        output_dir: Path,
        include_mp3: bool = True,
        include_markdown: bool = True,
        max_workers: int = 5,
    ) -> AudiobookDownloadResult:
        """下载有声书

        Args:
            alias_id: 有声书别名 ID
            output_dir: 输出目录
            include_mp3: 是否下载 MP3
            include_markdown: 是否生成 Markdown
            max_workers: 最大并发数

        Returns:
            下载结果
        """
        logger.info(f"开始下载有声书：{alias_id}")

        # 获取详情
        detail = self.client.get_audiobook_detail(alias_id)

        # 创建输出目录
        safe_title = self._sanitize_filename(detail.audiobook.title)
        book_dir = output_dir / safe_title
        book_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files: List[Path] = []
        failed_chapters: List[str] = []
        total_size = 0

        # 下载音频文件
        if include_mp3:
            audio_files, audio_failed, audio_size = self._download_audio(
                detail, book_dir, max_workers
            )
            downloaded_files.extend(audio_files)
            failed_chapters.extend(audio_failed)
            total_size += audio_size

        # 生成 Markdown
        if include_markdown:
            md_path = self._generate_markdown(detail, book_dir)
            if md_path:
                downloaded_files.append(md_path)

        logger.info(
            f"有声书下载完成：{detail.audiobook.title}，"
            f"成功 {len(downloaded_files)} 个文件，"
            f"失败 {len(failed_chapters)} 个章节"
        )

        return AudiobookDownloadResult(
            audiobook=detail.audiobook,
            output_dir=book_dir,
            downloaded_files=downloaded_files,
            failed_chapters=failed_chapters,
            total_size=total_size,
        )

    def _download_audio(
        self,
        detail: AudiobookDetail,
        output_dir: Path,
        max_workers: int,
    ) -> tuple[List[Path], List[str], int]:
        """下载音频文件

        Args:
            detail: 有声书详情
            output_dir: 输出目录
            max_workers: 最大并发数

        Returns:
            (下载的文件列表, 失败的章节ID列表, 总大小)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        downloaded_files: List[Path] = []
        failed_chapters: List[str] = []
        total_size = 0

        # 创建音频目录
        audio_dir = output_dir / "audio"
        audio_dir.mkdir(exist_ok=True)

        def download_chapter(chapter: AudiobookChapter, index: int) -> Optional[Path]:
            """下载单个章节"""
            if not chapter.audio_url:
                logger.warning(f"章节无音频 URL：{chapter.title}")
                return None

            # 文件名
            safe_title = self._sanitize_filename(chapter.title)
            filename = f"{index:03d}_{safe_title}.mp3"
            filepath = audio_dir / filename

            # 如果已存在，跳过
            if filepath.exists():
                logger.debug(f"音频已存在，跳过：{filepath}")
                return filepath

            try:
                # 下载
                response = self._session.get(chapter.audio_url, timeout=60)
                response.raise_for_status()

                filepath.write_bytes(response.content)
                logger.info(f"已下载：{filename}")
                return filepath

            except Exception as e:
                logger.error(f"下载失败：{chapter.title}，错误：{e}")
                return None

        # 并发下载
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(download_chapter, ch, idx): ch
                for idx, ch in enumerate(detail.chapters, 1)
                if ch.audio_url
            }

            for future in as_completed(futures):
                chapter = futures[future]
                try:
                    result = future.result()
                    if result:
                        downloaded_files.append(result)
                        total_size += result.stat().st_size
                    else:
                        failed_chapters.append(chapter.id)
                except Exception as e:
                    logger.error(f"下载任务异常：{chapter.title}，错误：{e}")
                    failed_chapters.append(chapter.id)

        return downloaded_files, failed_chapters, total_size

    def _generate_markdown(self, detail: AudiobookDetail, output_dir: Path) -> Optional[Path]:
        """生成 Markdown 文件

        Args:
            detail: 有声书详情
            output_dir: 输出目录

        Returns:
            Markdown 文件路径
        """
        try:
            safe_title = self._sanitize_filename(detail.audiobook.title)
            md_path = output_dir / f"{safe_title}.md"

            lines = [
                f"# {detail.audiobook.title}",
                "",
                f"**作者**: {detail.audiobook.author}",
                f"**朗读者**: {detail.audiobook.reader}",
                f"**简介**: {detail.audiobook.summary}",
                "",
                "---",
                "",
                "## 目录",
                "",
            ]

            # 添加章节
            for idx, chapter in enumerate(detail.chapters, 1):
                lines.append(f"{idx}. {chapter.title}")

            lines.extend(["", "---", "", "## 正文", ""])

            for idx, chapter in enumerate(detail.chapters, 1):
                lines.extend([
                    f"### {idx}. {chapter.title}",
                    "",
                    chapter.content if chapter.content else "*（此章节无文字内容）*",
                    "",
                ])

            md_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info(f"已生成 Markdown：{md_path}")
            return md_path

        except Exception as e:
            logger.error(f"生成 Markdown 失败：{e}")
            return None

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理文件名"""
        import re
        # 移除非法字符
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # 限制长度
        return name[:100].strip()
