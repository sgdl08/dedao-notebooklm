"""测试得到 API 客户端"""

import base64
import pytest
from pathlib import Path
from Crypto.Cipher import AES
from PIL import Image
import io

# 引入待测试的模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import dedao.ebook.client as ebook_client_module

from dedao.models import Course, Chapter, CourseDetail, EbookCatalog, EbookDetail, EbookInfo, EbookPage
from dedao import DedaoAPIError
from dedao.auth import DedaoAuth
from dedao.ebook.client import EbookClient
from dedao.ebook.downloader import EbookDownloader, SemanticBlock, SvgImageItem
from converter.html_to_md import HTMLToMarkdownConverter
from utils.crypto import decrypt_ebook_content


class TestCourseModel:
    """测试课程模型"""

    def test_course_creation(self):
        """测试课程创建"""
        course = Course(
            id="123",
            title="测试课程",
            author="测试作者",
            chapter_count=10
        )
        assert course.id == "123"
        assert course.title == "测试课程"
        assert course.chapter_count == 10


class TestChapterModel:
    """测试章节模型"""

    def test_chapter_creation(self):
        """测试章节创建"""
        chapter = Chapter(
            id="1",
            course_id="123",
            title="第一章",
            sort_order=1
        )
        assert chapter.id == "1"
        assert chapter.title == "第一章"
        assert chapter.sort_order == 1


class TestCourseDetail:
    """测试课程详情"""

    def test_course_detail(self):
        """测试课程详情"""
        course = Course(id="123", title="测试课程")
        chapters = [
            Chapter(id="1", course_id="123", title="第一章"),
            Chapter(id="2", course_id="123", title="第二章"),
        ]
        detail = CourseDetail(course=course, chapters=chapters)

        assert detail.total_chapters == 2
        assert detail.has_audio is False


class TestHTMLToMarkdown:
    """测试 HTML 转 Markdown"""

    def test_convert_basic(self):
        """测试基本转换"""
        converter = HTMLToMarkdownConverter()

        html = "<h1>标题</h1><p>这是一段文字</p>"
        expected = "# 标题\n\n这是一段文字"

        result = converter.convert(html)
        assert "标题" in result
        assert "这是一段文字" in result

    def test_convert_links(self):
        """测试链接转换"""
        converter = HTMLToMarkdownConverter()

        html = '<a href="https://example.com">链接</a>'
        result = converter.convert(html)

        assert "[链接]" in result
        assert "(https://example.com)" in result

    def test_convert_bold(self):
        """测试粗体转换"""
        converter = HTMLToMarkdownConverter()

        html = "<strong>粗体</strong>"
        result = converter.convert(html)

        assert "**粗体**" in result

    def test_empty_input(self):
        """测试空输入"""
        converter = HTMLToMarkdownConverter()
        assert converter.convert("") == ""


class TestDedaoAuth:
    """测试得到认证"""

    def test_auth_creation(self):
        """测试认证创建"""
        auth = DedaoAuth(cookie="test-cookie")
        assert auth.is_authenticated() is True
        assert "test-cookie" in auth.headers.get("Cookie", "")

    def test_auth_no_cookie(self):
        """测试无 Cookie 情况"""
        # 使用临时路径避免读取已保存的配置
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = DedaoAuth(config_path=Path(tmpdir) / "config.json")
            assert auth.is_authenticated() is False


class TestEbookCrypto:
    """测试电子书解密。"""

    def test_decrypt_supports_32_byte_key(self):
        key = b"3e4r06tjkpjcevlbslr3d96gdb5ahbmo"
        iv = b"6fd89a1b3a7f48fb"
        plaintext = "<svg><text>专注的真相</text></svg>".encode("utf-8")
        pad = 16 - (len(plaintext) % 16)
        ciphertext = AES.new(key, AES.MODE_CBC, iv).encrypt(plaintext + bytes([pad]) * pad)
        encrypted = base64.b64encode(ciphertext).decode("utf-8")

        assert decrypt_ebook_content(encrypted) == "<svg><text>专注的真相</text></svg>"


class TestEbookClient:
    """测试电子书客户端。"""

    def test_get_ebook_info_parses_book_info_wrapper(self, monkeypatch):
        client = EbookClient(cookie="test=123")

        def fake_request(method, url, **kwargs):
            return {
                "c": {
                    "bookInfo": {
                        "toc": [{"href": "chapter-1#toc", "text": "第一章", "playOrder": 1}],
                        "orders": [{"chapterId": "chapter-1"}],
                        "pages": [{"cid": "chapter-1", "page_num": 1}],
                    }
                }
            }

        monkeypatch.setattr(client, "_request", fake_request)
        info = client.get_ebook_info("token-123")

        assert isinstance(info, EbookInfo)
        assert info.toc[0].title == "第一章"
        assert info.orders[0]["chapterId"] == "chapter-1"
        assert info.pages[0].chapter_id == "chapter-1"

    def test_get_ebook_pages_sends_render_config(self, monkeypatch):
        client = EbookClient(cookie="test=123")
        captured = {}

        def fake_request(method, url, **kwargs):
            captured["json"] = kwargs["json"]
            return {"c": {"is_end": True, "pages": [{"page_id": "1", "svg": "abc"}]}}

        monkeypatch.setattr(client, "_request", fake_request)
        pages, is_end = client.get_ebook_pages("chapter-1", "token-123")

        assert captured["json"]["orientation"] == 0
        assert captured["json"]["config"]["width"] == 30000
        assert pages[0].svg == "abc"
        assert is_end is True

    def test_get_ebook_pages_falls_back_on_engine_error(self, monkeypatch):
        client = EbookClient(cookie="test=123")
        captured = []

        def fake_request(method, url, **kwargs):
            captured.append(kwargs["json"])
            if len(captured) == 1:
                raise DedaoAPIError("svg generate failed in engine error!", code=4000)
            return {"c": {"is_end": True, "pages": [{"page_id": "1", "svg": "abc"}]}}

        monkeypatch.setattr(client, "_request", fake_request)
        pages, is_end = client.get_ebook_pages("chapter-1", "token-123", count=50)

        assert len(captured) == 2
        assert captured[0]["config"]["width"] == 30000
        assert captured[0]["count"] == 50
        assert captured[1]["config"]["width"] == 60000
        assert captured[1]["count"] == 20
        assert pages[0].svg == "abc"
        assert is_end is True

    def test_get_all_chapter_pages_advances_by_returned_page_count(self, monkeypatch):
        client = EbookClient(cookie="test=123")
        requested_indexes = []
        responses = [
            ([EbookPage(page_id=str(i), svg=f"enc-{i}", chapter_id="chapter-1") for i in range(20)], False),
            ([EbookPage(page_id=str(i), svg=f"enc-{i}", chapter_id="chapter-1") for i in range(20, 40)], False),
            ([EbookPage(page_id=str(i), svg=f"enc-{i}", chapter_id="chapter-1") for i in range(40, 45)], True),
        ]

        def fake_get_ebook_pages(chapter_id, token, index=0, count=20, offset=0):
            requested_indexes.append((index, count))
            return responses.pop(0)

        monkeypatch.setattr(client, "get_ebook_pages", fake_get_ebook_pages)
        monkeypatch.setattr(ebook_client_module, "decrypt_ebook_content", lambda value: f"svg:{value}")

        pages = client.get_all_chapter_pages("ebook-1", "chapter-1", "token-123", use_cache=False)

        assert requested_indexes == [(0, 50), (20, 50), (40, 50)]
        assert len(pages) == 45
        assert pages[0] == "svg:enc-0"
        assert pages[-1] == "svg:enc-44"


class TestEbookDownloader:
    """测试电子书下载器。"""

    def test_download_groups_split_chapters(self, tmp_path):
        class FakeClient:
            cookie = "test=123"

            def check_auth(self):
                return {"nick_name": "tester"}

            def resolve_ebook(self, ebook_id_or_title):
                return EbookDetail(
                    enid="enid-1",
                    title="测试电子书",
                    author="测试作者",
                    book_intro="测试简介",
                    catalog=[
                        EbookCatalog(
                            chapter_id="chapter-1#toc",
                            title="第一章",
                            extra={"href": "chapter-1#toc"},
                        )
                    ],
                    extra={"id": 1},
                )

            def get_ebook_read_token(self, enid):
                return "token-123"

            def get_ebook_info(self, token):
                return EbookInfo(
                    token=token,
                    orders=[
                        {"chapterId": "chapter-1"},
                        {"chapterId": "chapter-1-part2"},
                    ],
                )

            def get_all_chapter_pages(self, enid, chapter_id, token):
                if chapter_id == "chapter-1":
                    return [
                        "<svg><text x='0' y='10'>上半章</text></svg>",
                    ]
                return [
                    "<svg><text x='0' y='10'>下半章</text></svg>",
                ]

        downloader = EbookDownloader(client=FakeClient(), output_dir=tmp_path)
        result = downloader.download("测试电子书", output_format="md")

        assert result.success is True
        content = result.output_files[0].read_text(encoding="utf-8")
        assert content.count("## 第一章") == 1
        assert "上半章" in content
        assert "下半章" in content

    def test_download_markdown_keeps_images_and_builds_notebooklm_html(self, tmp_path, monkeypatch):
        class FakeResponse:
            def __init__(self, content: bytes):
                self.content = content

            def raise_for_status(self):
                return None

        class FakeClient:
            cookie = "test=123"

            def check_auth(self):
                return {"nick_name": "tester"}

            def resolve_ebook(self, ebook_id_or_title):
                return EbookDetail(
                    enid="enid-1",
                    title="图文电子书",
                    author="测试作者",
                    catalog=[
                        EbookCatalog(
                            chapter_id="chapter-1#toc",
                            title="图文章节",
                            extra={"href": "chapter-1#toc"},
                        )
                    ],
                    extra={"id": 1},
                )

            def get_ebook_read_token(self, enid):
                return "token-123"

            def get_ebook_info(self, token):
                return EbookInfo(token=token, orders=[{"chapterId": "chapter-1"}])

            def get_all_chapter_pages(self, enid, chapter_id, token):
                return [
                    """
                    <svg width='60000' height='200000'>
                      <text x='29000' y='120' top='100' width='2000' height='30'
                        style='font-size:22px;font-weight:bold;'>图文章节</text>
                      <image x='8000' y='6000' width='44000' height='30000'
                        href='https://example.com/figure.png' />
                    </svg>
                    """
                ]

        downloader = EbookDownloader(client=FakeClient(), output_dir=tmp_path)
        monkeypatch.setattr(downloader._http, "get", lambda url, timeout=30: FakeResponse(b"PNGDATA"))
        result = downloader.download("图文电子书", output_format="md")

        assert result.success is True
        md_path = next(path for path in result.output_files if path.suffix == ".md")
        notebooklm_path = next(path for path in result.output_files if path.name.endswith(".notebooklm.html"))
        md = md_path.read_text(encoding="utf-8")
        notebooklm_html = notebooklm_path.read_text(encoding="utf-8")

        assert "## 图文章节" in md
        assert "(images/img-" in md
        assert "data:image/png;base64" in notebooklm_html

    def test_download_markdown_recovers_headings_and_lists(self, tmp_path):
        class FakeClient:
            cookie = "test=123"

            def check_auth(self):
                return {"nick_name": "tester"}

            def resolve_ebook(self, ebook_id_or_title):
                return EbookDetail(
                    enid="enid-1",
                    title="列表电子书",
                    author="测试作者",
                    catalog=[
                        EbookCatalog(
                            chapter_id="chapter-1#toc",
                            title="第一章",
                            extra={"href": "chapter-1#toc"},
                        )
                    ],
                    extra={"id": 1},
                )

            def get_ebook_read_token(self, enid):
                return "token-123"

            def get_ebook_info(self, token):
                return EbookInfo(token=token, orders=[{"chapterId": "chapter-1"}])

            def get_all_chapter_pages(self, enid, chapter_id, token):
                return [
                    """
                    <svg width='60000' height='200000'>
                      <text x='29600' y='120' top='100' width='800' height='22'
                        style='font-size:16px;font-weight:bold;'>第一章</text>
                      <text x='28000' y='180' top='150' width='4000' height='32'
                        style='font-size:22px;font-weight:bold;'>方法清单</text>
                      <text x='9000' y='420' top='395' width='6000' height='22'
                        style='font-size:16px;'>1. 第一项</text>
                      <text x='9000' y='490' top='465' width='6000' height='22'
                        style='font-size:16px;'>2. 第二项</text>
                    </svg>
                    """
                ]

        downloader = EbookDownloader(client=FakeClient(), output_dir=tmp_path)
        result = downloader.download("列表电子书", output_format="md")

        assert result.success is True
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "### 方法清单" in content
        assert "1. 第一项" in content
        assert "2. 第二项" in content

    def test_download_markdown_turns_table_pages_into_images(self, tmp_path):
        class FakeClient:
            cookie = "test=123"

            def check_auth(self):
                return {"nick_name": "tester"}

            def resolve_ebook(self, ebook_id_or_title):
                return EbookDetail(
                    enid="enid-1",
                    title="表格电子书",
                    author="测试作者",
                    catalog=[
                        EbookCatalog(
                            chapter_id="chapter-1#toc",
                            title="表格章节",
                            extra={"href": "chapter-1#toc"},
                        )
                    ],
                    extra={"id": 1},
                )

            def get_ebook_read_token(self, enid):
                return "token-123"

            def get_ebook_info(self, token):
                return EbookInfo(token=token, orders=[{"chapterId": "chapter-1"}])

            def get_all_chapter_pages(self, enid, chapter_id, token):
                return [
                    """
                    <svg width='60000' height='200000'>
                      <rect x='5000' y='5000' width='50000' height='1' stroke='black' />
                      <rect x='5000' y='10000' width='50000' height='1' stroke='black' />
                      <rect x='5000' y='15000' width='50000' height='1' stroke='black' />
                      <rect x='5000' y='20000' width='50000' height='1' stroke='black' />
                      <rect x='5000' y='5000' width='1' height='15000' stroke='black' />
                      <rect x='30000' y='5000' width='1' height='15000' stroke='black' />
                      <text x='8000' y='8200' top='8000' width='2000' height='22'
                        style='font-size:16px;'>列1</text>
                      <text x='33000' y='8200' top='8000' width='2000' height='22'
                        style='font-size:16px;'>列2</text>
                    </svg>
                    """
                ]

        downloader = EbookDownloader(client=FakeClient(), output_dir=tmp_path)
        result = downloader.download("表格电子书", output_format="md")

        assert result.success is True
        content = result.output_files[0].read_text(encoding="utf-8")
        table_assets = list((tmp_path / "表格电子书" / "images").glob("table-*.svg"))

        assert "(images/table-" in content
        assert table_assets

    def test_small_repeated_icons_are_filtered(self, tmp_path):
        class FakeClient:
            cookie = "test=123"

            def check_auth(self):
                return {"nick_name": "tester"}

            def resolve_ebook(self, ebook_id_or_title):
                return EbookDetail(
                    enid="enid-1",
                    title="图标电子书",
                    author="测试作者",
                    catalog=[
                        EbookCatalog(
                            chapter_id="chapter-1#toc",
                            title="引言",
                            extra={"href": "chapter-1#toc"},
                        )
                    ],
                    extra={"id": 1},
                )

            def get_ebook_read_token(self, enid):
                return "token-123"

            def get_ebook_info(self, token):
                return EbookInfo(token=token, orders=[{"chapterId": "chapter-1"}])

            def get_all_chapter_pages(self, enid, chapter_id, token):
                icons = "\n".join(
                    f"<image x='8000' y='{6000 + i * 5000}' width='3000' height='3000' href='https://example.com/note.png' />"
                    for i in range(5)
                )
                return [
                    f"""
                    <svg width='60000' height='200000'>
                      <text x='9000' y='120' top='100' width='6000' height='22'
                        style='font-size:16px;'>正文内容</text>
                      {icons}
                    </svg>
                    """
                ]

        downloader = EbookDownloader(client=FakeClient(), output_dir=tmp_path)
        result = downloader.download("图标电子书", output_format="md")

        assert result.success is True
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "正文内容" in content
        assert "![" not in content

    def test_chapter_opener_decorative_image_is_suppressed_and_duplicate_title_trimmed(self, tmp_path, monkeypatch):
        class FakeResponse:
            def __init__(self, content: bytes):
                self.content = content
                self.headers = {"content-type": "image/png"}
                self.text = content.decode("utf-8", errors="ignore")

            def raise_for_status(self):
                return None

        downloader = EbookDownloader(output_dir=tmp_path)
        monkeypatch.setattr(downloader._http, "get", lambda url, timeout=30: FakeResponse(b"PNGDATA"))

        images_dir = tmp_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        svg = """
        <svg width='60000' height='200000'>
          <text x='28600' y='120' top='100' width='2600' height='22'
            style='font-size:16px;'>·第2章·</text>
          <text x='22800' y='240' top='220' width='14400' height='44'
            style='font-size:32px;font-weight:bold;'>蓝色巨人</text>
          <text x='26200' y='330' top='310' width='7600' height='32'
            style='font-size:24px;'>IBM公司</text>
          <image x='0' y='46657' width='60000' height='106666'
            href='https://example.com/chapter-opener.png' />
        </svg>
        """

        blocks = downloader._render_page_blocks(svg, images_dir, "第2章 蓝色巨人 IBM公司", 1)

        assert [block.kind for block in blocks] == ["paragraph", "heading", "heading"]
        assert not any(block.kind == "image" for block in blocks)
        assert downloader._trim_leading_title_blocks("第2章 蓝色巨人 IBM公司", blocks) == []

    def test_small_inline_images_stay_inline(self, tmp_path, monkeypatch):
        svg_payload = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 30'><text x='0' y='20'>x</text></svg>"

        class FakeResponse:
            def __init__(self, content: bytes, text: str = "", headers=None):
                self.content = content
                self.text = text or content.decode("utf-8", errors="ignore")
                self.headers = headers or {}

            def raise_for_status(self):
                return None

        class FakeClient:
            cookie = "test=123"

            def check_auth(self):
                return {"nick_name": "tester"}

            def resolve_ebook(self, ebook_id_or_title):
                return EbookDetail(
                    enid="enid-1",
                    title="公式电子书",
                    author="测试作者",
                    catalog=[
                        EbookCatalog(
                            chapter_id="chapter-1#toc",
                            title="公式章节",
                            extra={"href": "chapter-1#toc"},
                        )
                    ],
                    extra={"id": 1},
                )

            def get_ebook_read_token(self, enid):
                return "token-123"

            def get_ebook_info(self, token):
                return EbookInfo(token=token, orders=[{"chapterId": "chapter-1"}])

            def get_all_chapter_pages(self, enid, chapter_id, token):
                return [
                    """
                    <svg width='60000' height='200000'>
                      <text x='9000' y='420' top='395' width='5000' height='22'
                        style='font-size:16px;'>α ≤</text>
                      <image x='15000' y='380' width='2500' height='1000' href='https://example.com/formula.svg' />
                      <text x='18000' y='420' top='395' width='5000' height='22'
                        style='font-size:16px;'>成立</text>
                    </svg>
                    """
                ]

        downloader = EbookDownloader(client=FakeClient(), output_dir=tmp_path)
        monkeypatch.setattr(
            downloader._http,
            "get",
            lambda url, timeout=30: FakeResponse(
                svg_payload.encode("utf-8"),
                text=svg_payload,
                headers={"content-type": "image/svg+xml"},
            ),
        )
        result = downloader.download("公式电子书", output_format="md")

        assert result.success is True
        content = result.output_files[0].read_text(encoding="utf-8")
        assert "α ≤" in content
        assert "成立" in content
        # 行内公式图片应以 <img> 标签形式嵌入（非 markdown 图片语法）
        assert '<img src="' in content or "![" in content

    def test_heading_and_list_inline_images_render_without_tokens(self, tmp_path, monkeypatch):
        svg_payload = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 30'><text x='0' y='20'>x</text></svg>"

        class FakeResponse:
            def __init__(self, content: bytes, text: str = "", headers=None):
                self.content = content
                self.text = text or content.decode("utf-8", errors="ignore")
                self.headers = headers or {}

            def raise_for_status(self):
                return None

        class FakeClient:
            cookie = "test=123"

            def check_auth(self):
                return {"nick_name": "tester"}

            def resolve_ebook(self, ebook_id_or_title):
                return EbookDetail(
                    enid="enid-1",
                    title="标题公式电子书",
                    author="测试作者",
                    catalog=[
                        EbookCatalog(
                            chapter_id="chapter-1#toc",
                            title="章节一",
                            extra={"href": "chapter-1#toc"},
                        )
                    ],
                    extra={"id": 1},
                )

            def get_ebook_read_token(self, enid):
                return "token-123"

            def get_ebook_info(self, token):
                return EbookInfo(token=token, orders=[{"chapterId": "chapter-1"}])

            def get_all_chapter_pages(self, enid, chapter_id, token):
                return [
                    """
                    <svg width='60000' height='200000'>
                      <text x='28000' y='180' top='150' width='2800' height='32'
                        style='font-size:22px;font-weight:bold;'>标题</text>
                      <image x='31000' y='154' width='180' height='22' href='https://example.com/formula.svg' />
                      <text x='31350' y='180' top='150' width='2800' height='32'
                        style='font-size:22px;font-weight:bold;'>继续</text>

                      <text x='9000' y='420' top='395' width='2600' height='22'
                        style='font-size:16px;'>1. 条目</text>
                      <image x='11650' y='399' width='160' height='20' href='https://example.com/list.svg' />
                      <text x='11900' y='420' top='395' width='2600' height='22'
                        style='font-size:16px;'>后缀</text>
                    </svg>
                    """
                ]

        downloader = EbookDownloader(client=FakeClient(), output_dir=tmp_path)
        monkeypatch.setattr(
            downloader._http,
            "get",
            lambda url, timeout=30: FakeResponse(
                svg_payload.encode("utf-8"),
                text=svg_payload,
                headers={"content-type": "image/svg+xml"},
            ),
        )
        result = downloader.download("标题公式电子书", output_format="md")

        assert result.success is True
        md_path = next(path for path in result.output_files if path.suffix == ".md")
        notebooklm_path = next(path for path in result.output_files if path.name.endswith(".notebooklm.html"))
        md = md_path.read_text(encoding="utf-8")
        notebooklm_html = notebooklm_path.read_text(encoding="utf-8")

        assert "@@INLINE_IMG_" not in notebooklm_html
        assert "<h3>标题" in notebooklm_html and 'class="inline-image"' in notebooklm_html
        assert "<li>条目" in notebooklm_html and 'class="inline-image"' in notebooklm_html
        assert "### 标题" in md or "标题" in md
        assert "条目" in md

    def test_trim_leading_title_blocks_removes_split_duplicate_title(self, tmp_path):
        downloader = EbookDownloader(output_dir=tmp_path)
        blocks = [
            SemanticBlock(kind="paragraph", y=10.0, text="35"),
            SemanticBlock(kind="heading", y=20.0, text="“真正的男人要有晶圆厂”", level=4),
            SemanticBlock(kind="paragraph", y=30.0, text="正文开始"),
        ]

        trimmed = downloader._trim_leading_title_blocks("35 “真正的男人要有晶圆厂”", blocks)

        assert len(trimmed) == 1
        assert trimmed[0].text == "正文开始"

    def test_drop_duplicate_heading_blocks_removes_catalog_heading_echo(self, tmp_path):
        downloader = EbookDownloader(output_dir=tmp_path)
        blocks = [
            SemanticBlock(kind="paragraph", y=10.0, text="这一段是章节导语。"),
            SemanticBlock(kind="heading", y=20.0, text="1 赶上机械革命的最后一次浪潮", level=4),
            SemanticBlock(kind="paragraph", y=30.0, text="正文继续。"),
        ]

        filtered = downloader._drop_duplicate_heading_blocks("1 赶上机械革命的最后一次浪潮", blocks)

        assert [block.kind for block in filtered] == ["paragraph", "paragraph"]
        assert filtered[0].text == "这一段是章节导语。"
        assert filtered[1].text == "正文继续。"

    def test_raw_xhtml_fallback_title_is_not_rendered_as_heading(self, tmp_path):
        downloader = EbookDownloader(output_dir=tmp_path)
        chapter = type(
            "Chapter",
            (),
            {
                "title": "Section0037.xhtml",
                "svg_contents": ["<svg width='60000' height='200000'><text x='9000' y='420' top='395' width='8000' height='22' style='font-size:16px;'>正文保留</text></svg>"],
                "html_content": "",
                "markdown_content": "",
            },
        )()
        book_dir = tmp_path / "book"
        book_dir.mkdir(parents=True, exist_ok=True)

        html = downloader._render_chapter_html(book_dir, chapter, embed_assets=False)

        assert "<h2>Section0037.xhtml</h2>" not in html
        assert "<p>正文保留</p>" in html

    def test_raw_xhtml_fallback_title_does_not_leak_into_image_alt_or_caption(self, tmp_path, monkeypatch):
        class FakeResponse:
            def __init__(self, content: bytes):
                self.content = content
                self.headers = {"content-type": "image/png"}
                self.text = content.decode("utf-8", errors="ignore")

            def raise_for_status(self):
                return None

        downloader = EbookDownloader(output_dir=tmp_path)
        monkeypatch.setattr(downloader._http, "get", lambda url, timeout=30: FakeResponse(b"PNGDATA"))
        chapter = type(
            "Chapter",
            (),
            {
                "title": "Section0034.xhtml",
                "svg_contents": [
                    """
                    <svg width='60000' height='200000'>
                      <text x='9000' y='420' top='395' width='8000' height='22' style='font-size:16px;'>正文保留</text>
                      <image x='8000' y='6000' width='10000' height='10000' href='https://example.com/figure.png' />
                    </svg>
                    """
                ],
                "html_content": "",
                "markdown_content": "",
            },
        )()
        book_dir = tmp_path / "book"
        book_dir.mkdir(parents=True, exist_ok=True)

        html = downloader._render_chapter_html(book_dir, chapter, embed_assets=False)

        assert "Section0034.xhtml" not in html
        assert "<figcaption>" not in html

    def test_inline_row_matching_is_strict_and_square_raster_is_not_formula(self, tmp_path):
        downloader = EbookDownloader(output_dir=tmp_path)

        assert downloader._find_inline_image_row(
            SvgImageItem("https://example.com/formula.svg", 100.0, 105.0, 180.0, 20.0),
            [100.0, 200.0],
        ) == 100.0
        assert downloader._find_inline_image_row(
            SvgImageItem("https://example.com/figure.jpg", 100.0, 149.0, 900.0, 300.0),
            [105.0],
        ) is None
        assert downloader._is_formula_like_inline_image(
            SvgImageItem("https://example.com/icon.png", 0.0, 0.0, 72.0, 72.0)
        ) is False
        assert downloader._is_formula_like_inline_image(
            SvgImageItem("https://example.com/formula.svg", 0.0, 0.0, 72.0, 72.0)
        ) is True
        assert downloader._is_tiny_square_raster_icon(
            SvgImageItem("https://example.com/icon.png", 0.0, 0.0, 72.0, 72.0)
        ) is True

    def test_write_svg_asset_inlines_nested_remote_images(self, tmp_path, monkeypatch):
        png = io.BytesIO()
        Image.new("RGB", (2, 2), (255, 255, 255)).save(png, format="PNG")
        png_bytes = png.getvalue()

        class FakeResponse:
            def __init__(self, content: bytes, headers=None):
                self.content = content
                self.headers = headers or {"content-type": "image/png"}
                self.text = content.decode("utf-8", errors="ignore")

            def raise_for_status(self):
                return None

        downloader = EbookDownloader(output_dir=tmp_path)
        monkeypatch.setattr(
            downloader._http,
            "get",
            lambda url, timeout=30: FakeResponse(png_bytes),
        )
        images_dir = tmp_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        src = downloader._write_svg_asset(
            "<svg xmlns='http://www.w3.org/2000/svg'><image href='https://example.com/nested.png' x='0' y='0' width='10' height='10' /></svg>",
            images_dir,
            "table",
        )

        saved = (tmp_path / src).read_text(encoding="utf-8")
        assert "data:image/png;base64," in saved

    def test_write_svg_asset_rewrites_stale_existing_file(self, tmp_path, monkeypatch):
        png = io.BytesIO()
        Image.new("RGB", (2, 2), (255, 255, 255)).save(png, format="PNG")
        png_bytes = png.getvalue()

        class FakeResponse:
            def __init__(self, content: bytes, headers=None):
                self.content = content
                self.headers = headers or {"content-type": "image/png"}
                self.text = content.decode("utf-8", errors="ignore")

            def raise_for_status(self):
                return None

        downloader = EbookDownloader(output_dir=tmp_path)
        monkeypatch.setattr(
            downloader._http,
            "get",
            lambda url, timeout=30: FakeResponse(png_bytes),
        )
        images_dir = tmp_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        svg = "<svg xmlns='http://www.w3.org/2000/svg'><image href='https://example.com/nested.png' x='0' y='0' width='10' height='10' /></svg>"
        src = downloader._write_svg_asset(svg, images_dir, "table")
        target = tmp_path / src
        target.write_text(svg, encoding="utf-8")

        downloader._write_svg_asset(svg, images_dir, "table")

        saved = target.read_text(encoding="utf-8")
        assert "data:image/png;base64," in saved

    def test_path_heavy_page_is_not_misclassified_as_table(self, tmp_path):
        downloader = EbookDownloader(output_dir=tmp_path)

        lines = [
            type("Line", (), {"text": f"第{i}行"})()
            for i in range(10)
        ]
        shape_stats = {"horizontal": 0, "vertical": 0, "paths": 22, "total": 22}

        assert downloader._is_probable_table_page(shape_stats, lines) is False

    def test_prose_heavy_page_is_not_misclassified_as_table(self, tmp_path):
        downloader = EbookDownloader(output_dir=tmp_path)

        lines = [
            type("Line", (), {"text": text})()
            for text in [
                "IBM在大型机时代建立了难以撼动的行业地位，并且塑造了现代企业计算的基本范式。",
                "在随后的个人电脑浪潮中，它既受益于开放生态，也逐渐失去了对产业节奏的绝对控制。",
                "真正重要的是，这家公司总能在危机中重组自己的组织能力，并寻找新的利润来源。",
                "很多管理者把IBM看成保守公司的代表，但它其实长期扮演了产业基础设施提供者的角色。",
                "这也是为什么讨论蓝色巨人时，不能只看单次产品成败，而要看它在技术周期中的位置。",
                "如果一页里已经存在大量连续正文，就不应该因为版面线条较多而把整页压成一张表格图。",
                "内容优先意味着先保留可检索文本，再把图片和复杂表格作为补充信息处理。",
            ]
        ]
        shape_stats = {"horizontal": 100, "vertical": 8, "paths": 0, "total": 108}

        assert downloader._is_probable_table_page(shape_stats, lines) is False
