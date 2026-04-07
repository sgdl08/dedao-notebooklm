"""电子书下载模块

提供电子书的列表获取、详情查询和下载功能。
支持 AES-CBC 解密电子书内容。
"""

import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import EbookDetail, EbookChapter, EbookCatalog, EbookPage, EbookInfo
from .client import DedaoClient, DedaoAPIError
from .cache import get_cache, CachePrefix, CacheTTL

# 尝试从 utils 导入，如果失败则定义一个本地版本
try:
    from utils.crypto import decrypt_ebook_content
except ImportError:
    import base64

    def pkcs7_unpad(data: bytes) -> bytes:
        if not data:
            return data
        length = len(data)
        unpadding = data[length - 1]
        if unpadding > length or unpadding == 0:
            return data
        for i in range(1, unpadding + 1):
            if data[length - i] != unpadding:
                return data
        return data[:length - unpadding]

    def decrypt_ebook_content(encrypted_svg: str, key: str = None, iv: str = None) -> str:
        DEFAULT_AES_KEY = "3e4r06tjkpjcevlbslr3d96gdb5ahbmo"
        DEFAULT_AES_IV = "6fd89a1b3a7f48fb"
        key = key or DEFAULT_AES_KEY
        iv = iv or DEFAULT_AES_IV
        if not encrypted_svg:
            return ""
        try:
            ciphertext = base64.b64decode(encrypted_svg)
        except Exception:
            return ""
        try:
            from Crypto.Cipher import AES
            key_bytes = key.encode('utf-8')[:16].ljust(16, b'\0')
            iv_bytes = iv.encode('utf-8')[:16].ljust(16, b'\0')
            cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
            plaintext = cipher.decrypt(ciphertext)
            plaintext = pkcs7_unpad(plaintext)
            return plaintext.decode('utf-8')
        except Exception:
            return ""

logger = logging.getLogger(__name__)


class EbookClient(DedaoClient):
    """电子书 API 客户端

    继承自 DedaoClient，添加电子书特定的 API 方法。
    """

    def get_ebook_list(self, page: int = 1, page_size: int = 20) -> List[EbookDetail]:
        """获取已购电子书列表

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            电子书列表
        """
        logger.info(f"获取已购电子书列表 (第 {page} 页)...")

        # POST /api/hades/v2/product/list
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/api/hades/v2/product/list",
            json={
                "page": page,
                "page_size": page_size,
                "type": "ebook",  # 电子书类型
            },
            headers=headers,
        )

        ebooks = []
        items = data.get("c", {}).get("list", []) or data.get("list", [])

        for item in items:
            ebook = EbookDetail(
                enid=str(item.get("enid") or item.get("id", "")),
                title=item.get("name") or item.get("title", "未知电子书"),
                cover=item.get("logo") or item.get("cover", ""),
                author=item.get("author_name") or item.get("author", ""),
                book_intro=item.get("intro", ""),
                is_vip_book=item.get("is_vip", False),
                extra=item,
            )
            ebooks.append(ebook)

        logger.info(f"找到 {len(ebooks)} 本电子书")
        return ebooks

    def get_ebook_detail(self, enid: str) -> EbookDetail:
        """获取电子书详情

        Args:
            enid: 电子书 ID

        Returns:
            电子书详情
        """
        logger.info(f"获取电子书详情：{enid}")

        # 检查缓存
        cache = get_cache()
        cache_key = f"{CachePrefix.EBOOK}detail:{enid}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"使用缓存的电子书详情：{enid}")
            return self._dict_to_ebook_detail(cached)

        # GET /pc/ebook2/v1/pc/detail?id={enid}
        data = self._request("GET", f"/pc/ebook2/v1/pc/detail?id={enid}")

        # 解析响应
        book_data = data.get("c", {}) or data.get("data", {})

        # 目录
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
            title=book_data.get("operating_title") or book_data.get("title") or book_data.get("name", "未知电子书"),
            cover=book_data.get("cover") or book_data.get("logo", ""),
            author=book_data.get("book_author") or book_data.get("author_name") or book_data.get("author", ""),
            author_info=book_data.get("author_intro", ""),
            book_intro=book_data.get("book_intro") or book_data.get("intro", ""),
            publish_time=book_data.get("publish_time", ""),
            is_vip_book=book_data.get("is_vip", False),
            price=book_data.get("price"),
            catalog=catalog,
            extra=book_data,
        )

        # 缓存结果
        cache.set(cache_key, self._ebook_detail_to_dict(ebook), CacheTTL.COURSE_DETAIL)

        logger.info(f"电子书包含 {len(catalog)} 个目录项")
        return ebook

    def get_ebook_read_token(self, enid: str) -> str:
        """获取电子书阅读令牌

        Args:
            enid: 电子书 ID

        Returns:
            阅读令牌
        """
        logger.debug(f"获取电子书阅读令牌：{enid}")

        # POST /api/pc/ebook2/v1/pc/read/token
        # 注意：参数名是 id 而不是 enid
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/api/pc/ebook2/v1/pc/read/token",
            json={"id": enid},
            headers=headers,
        )

        token = data.get("c", {}).get("token") or data.get("token", "")
        if not token:
            raise DedaoAPIError("获取阅读令牌失败")

        return token

    def get_ebook_info(self, token: str) -> EbookInfo:
        """获取电子书阅读信息

        Args:
            token: 阅读令牌

        Returns:
            电子书信息（目录、页码顺序等）
        """
        logger.debug("获取电子书阅读信息...")

        # GET /ebk_web/v1/get_book_info?token={token}
        data = self._request("GET", f"/ebk_web/v1/get_book_info?token={token}")

        book_info = data.get("book_info", {}) or data.get("data", {})

        # 目录
        toc = []
        toc_list = book_info.get("toc", [])
        for item in toc_list:
            toc.append(EbookCatalog(
                chapter_id=str(item.get("chapter_id", "")),
                title=item.get("title", ""),
                level=item.get("level", 0),
                order=item.get("order", 0),
                extra=item,
            ))

        # 页码顺序
        orders = book_info.get("orders", [])

        return EbookInfo(
            token=token,
            toc=toc,
            orders=orders,
            pages=[],
        )

    def get_ebook_pages(
        self,
        chapter_id: str,
        token: str,
        index: int = 0,
        count: int = 20,
        offset: int = 0,
    ) -> tuple[List[EbookPage], bool]:
        """获取电子书页面内容

        Args:
            chapter_id: 章节 ID
            token: 阅读令牌
            index: 起始索引
            count: 获取数量
            offset: 偏移量

        Returns:
            (页面列表, 是否结束)
        """
        logger.debug(f"获取电子书页面：章节 {chapter_id}，索引 {index}")

        # POST /ebk_web_go/v2/get_pages
        headers = {"Content-Type": "application/json"}
        data = self._request(
            "POST",
            "/ebk_web_go/v2/get_pages",
            json={
                "chapter_id": chapter_id,
                "token": token,
                "index": index,
                "count": count,
                "offset": offset,
            },
            headers=headers,
        )

        page_list = data.get("page_list", {}) or data.get("data", {})
        pages_data = page_list.get("pages", [])
        is_end = page_list.get("is_end", True)

        pages = []
        for page_data in pages_data:
            pages.append(EbookPage(
                page_id=str(page_data.get("page_id", "")),
                svg=page_data.get("svg", ""),
                chapter_id=chapter_id,
            ))

        return pages, is_end

    def get_all_chapter_pages(
        self,
        enid: str,
        chapter_id: str,
        token: str,
        use_cache: bool = True,
    ) -> List[str]:
        """获取章节所有页面内容（解密后）

        Args:
            enid: 电子书 ID
            chapter_id: 章节 ID
            token: 阅读令牌
            use_cache: 是否使用缓存

        Returns:
            解密后的 SVG 内容列表
        """
        cache = get_cache()
        cache_key = f"{CachePrefix.EBOOK_PAGE}{enid}:{chapter_id}"

        # 检查缓存
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"使用缓存的章节页面：{chapter_id}")
                return cached

        logger.info(f"下载章节：{chapter_id}")

        all_svg_contents = []
        index, count, offset = 0, 20, 0

        while True:
            # 限流：避免请求过快
            time.sleep(0.1)

            pages, is_end = self.get_ebook_pages(chapter_id, token, index, count, offset)

            for page in pages:
                # 解密 SVG 内容
                decrypted_svg = decrypt_ebook_content(page.svg)
                if decrypted_svg:
                    all_svg_contents.append(decrypted_svg)

            if is_end:
                break

            index += count

        logger.info(f"章节 {chapter_id} 下载完成（共 {len(all_svg_contents)} 页）")

        # 缓存结果
        if use_cache and all_svg_contents:
            cache.set(cache_key, all_svg_contents, CacheTTL.EBOOK_PAGE)

        return all_svg_contents

    def _ebook_detail_to_dict(self, ebook: EbookDetail) -> Dict[str, Any]:
        """转换电子书详情为字典"""
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
        }

    def _dict_to_ebook_detail(self, data: Dict[str, Any]) -> EbookDetail:
        """从字典创建电子书详情"""
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
        )


@dataclass
class EbookDownloadResult:
    """电子书下载结果"""
    ebook: EbookDetail
    output_dir: Path
    downloaded_files: List[Path]
    failed_chapters: List[str]


class EbookDownloader:
    """电子书下载器

    功能：
    - 下载电子书内容
    - 生成 Markdown 文件
    - 生成 HTML 文件
    - 生成 EPUB 文件（可选）
    """

    def __init__(self, client: Optional[EbookClient] = None):
        """初始化下载器

        Args:
            client: 电子书客户端
        """
        self.client = client or EbookClient()

    def download(
        self,
        enid: str,
        output_dir: Path,
        output_format: str = "markdown",  # markdown, html, epub
        max_workers: int = 5,
    ) -> EbookDownloadResult:
        """下载电子书

        Args:
            enid: 电子书 ID
            output_dir: 输出目录
            output_format: 输出格式
            max_workers: 最大并发数

        Returns:
            下载结果
        """
        logger.info(f"开始下载电子书：{enid}")

        # 获取详情
        ebook = self.client.get_ebook_detail(enid)

        # 获取阅读令牌和信息
        token = self.client.get_ebook_read_token(enid)
        ebook_info = self.client.get_ebook_info(token)

        # 创建输出目录
        safe_title = self._sanitize_filename(ebook.title)
        book_dir = output_dir / safe_title
        book_dir.mkdir(parents=True, exist_ok=True)

        # 下载所有章节
        chapters = self._download_chapters(
            enid, ebook_info, token, max_workers
        )

        downloaded_files: List[Path] = []
        failed_chapters: List[str] = []

        # 根据格式生成输出
        if output_format in ("markdown", "md"):
            md_path = self._generate_markdown(ebook, chapters, book_dir)
            if md_path:
                downloaded_files.append(md_path)

        if output_format == "html":
            html_path = self._generate_html(ebook, chapters, book_dir)
            if html_path:
                downloaded_files.append(html_path)

        if output_format == "epub":
            epub_path = self._generate_epub(ebook, chapters, book_dir)
            if epub_path:
                downloaded_files.append(epub_path)

        logger.info(
            f"电子书下载完成：{ebook.title}，"
            f"成功 {len(downloaded_files)} 个文件"
        )

        return EbookDownloadResult(
            ebook=ebook,
            output_dir=book_dir,
            downloaded_files=downloaded_files,
            failed_chapters=failed_chapters,
        )

    def _download_chapters(
        self,
        enid: str,
        ebook_info: EbookInfo,
        token: str,
        max_workers: int,
    ) -> List[EbookChapter]:
        """下载所有章节

        Args:
            enid: 电子书 ID
            ebook_info: 电子书信息
            token: 阅读令牌
            max_workers: 最大并发数

        Returns:
            章节列表
        """
        chapters: List[EbookChapter] = []
        orders = ebook_info.orders

        def download_chapter(order_data: Dict[str, Any], index: int) -> Optional[EbookChapter]:
            """下载单个章节"""
            chapter_id = order_data.get("chapter_id", "")
            if not chapter_id:
                return None

            try:
                svg_contents = self.client.get_all_chapter_pages(
                    enid, chapter_id, token
                )

                # 查找对应的目录标题
                title = f"第 {index} 章"
                for toc_item in ebook_info.toc:
                    if toc_item.chapter_id == chapter_id:
                        title = toc_item.title
                        break

                return EbookChapter(
                    chapter_id=chapter_id,
                    title=title,
                    order=index,
                    svg_contents=svg_contents,
                )

            except Exception as e:
                logger.error(f"下载章节失败：{chapter_id}，错误：{e}")
                return None

        # 并发下载
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(download_chapter, order, idx): order
                for idx, order in enumerate(orders, 1)
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        chapters.append(result)
                except Exception as e:
                    logger.error(f"下载任务异常：{e}")

        # 按顺序排序
        chapters.sort(key=lambda x: x.order)
        return chapters

    def _generate_markdown(
        self,
        ebook: EbookDetail,
        chapters: List[EbookChapter],
        output_dir: Path,
    ) -> Optional[Path]:
        """生成 Markdown 文件"""
        try:
            safe_title = self._sanitize_filename(ebook.title)
            md_path = output_dir / f"{safe_title}.md"

            lines = [
                f"# {ebook.title}",
                "",
                f"**作者**: {ebook.author}",
                "",
                f"**简介**: {ebook.book_intro}",
                "",
                "---",
                "",
                "## 目录",
                "",
            ]

            # 添加目录
            for chapter in chapters:
                lines.append(f"- {chapter.title}")

            lines.extend(["", "---", "", "## 正文", ""])

            # 添加章节内容
            for chapter in chapters:
                lines.extend([
                    f"### {chapter.title}",
                    "",
                ])

                # SVG 内容转换为文本
                for svg in chapter.svg_contents:
                    text = self._svg_to_text(svg)
                    if text:
                        lines.append(text)
                        lines.append("")

            md_path.write_text("\n".join(lines), encoding="utf-8")
            logger.info(f"已生成 Markdown：{md_path}")
            return md_path

        except Exception as e:
            logger.error(f"生成 Markdown 失败：{e}")
            return None

    def _generate_html(
        self,
        ebook: EbookDetail,
        chapters: List[EbookChapter],
        output_dir: Path,
    ) -> Optional[Path]:
        """生成 HTML 文件"""
        try:
            safe_title = self._sanitize_filename(ebook.title)
            html_path = output_dir / f"{safe_title}.html"

            html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ebook.title}</title>
    <style>
        body {{ font-family: serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ text-align: center; }}
        .author {{ text-align: center; color: #666; }}
        .intro {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
        chapter {{ margin-top: 30px; }}
        chapter-title {{ font-size: 1.5em; font-weight: bold; margin-bottom: 15px; }}
    </style>
</head>
<body>
    <h1>{ebook.title}</h1>
    <p class="author">作者：{ebook.author}</p>
    <div class="intro">
        <p><strong>简介</strong></p>
        <p>{ebook.book_intro}</p>
    </div>
"""

            for chapter in chapters:
                html_content += f"""
    <chapter>
        <chapter-title>{chapter.title}</chapter-title>
        <div class="content">
"""
                for svg in chapter.svg_contents:
                    # 直接使用 SVG 内容
                    html_content += svg

                html_content += """
        </div>
    </chapter>
"""

            html_content += """
</body>
</html>
"""

            html_path.write_text(html_content, encoding="utf-8")
            logger.info(f"已生成 HTML：{html_path}")
            return html_path

        except Exception as e:
            logger.error(f"生成 HTML 失败：{e}")
            return None

    def _generate_epub(
        self,
        ebook: EbookDetail,
        chapters: List[EbookChapter],
        output_dir: Path,
    ) -> Optional[Path]:
        """生成 EPUB 文件"""
        try:
            from ..converter.epub_generator import EPUBGenerator

            safe_title = self._sanitize_filename(ebook.title)
            epub_path = output_dir / f"{safe_title}.epub"

            generator = EPUBGenerator(
                title=ebook.title,
                author=ebook.author,
                cover_path=ebook.cover if ebook.cover else None,
            )

            for chapter in chapters:
                # SVG 转 HTML
                html_content = "\n".join(chapter.svg_contents)
                generator.add_chapter(chapter.title, html_content, chapter.order)

            generator.generate(epub_path)
            logger.info(f"已生成 EPUB：{epub_path}")
            return epub_path

        except ImportError:
            logger.warning("未安装 ebooklib，跳过 EPUB 生成")
            return None
        except Exception as e:
            logger.error(f"生成 EPUB 失败：{e}")
            return None

    def _svg_to_text(self, svg: str) -> str:
        """将 SVG 内容转换为纯文本

        简单提取文本内容，去除 SVG 标签。
        """
        import re
        # 移除 SVG 标签
        text = re.sub(r'<svg[^>]*>', '', svg)
        text = re.sub(r'</svg>', '', text)
        # 移除其他标签
        text = re.sub(r'<[^>]+>', '', text)
        # 清理空白
        text = text.strip()
        return text

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理文件名"""
        import re
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        return name[:100].strip()
