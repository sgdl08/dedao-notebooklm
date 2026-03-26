"""测试得到 API 客户端"""

import pytest
from pathlib import Path

# 引入待测试的模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dedao.models import Course, Chapter, CourseDetail
from dedao.auth import DedaoAuth
from dedao.client import DedaoClient
from converter.html_to_md import HTMLToMarkdownConverter


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


class TestArticlePagination:
    """测试文章分页边界处理"""

    def test_get_all_articles_does_not_skip_boundary_order(self):
        """回归：max_order_num 边界不能跳过 order=2"""

        class FakeDedaoClient(DedaoClient):
            def __init__(self):
                super().__init__(cookie="fake-cookie")
                # 生成 1..32 的文章，模拟 reverse=True 返回
                self._items = [
                    {
                        "enid": f"id-{i}",
                        "order_num": i,
                        "title": f"title-{i}",
                    }
                    for i in range(1, 33)
                ]

            def get_article_list(self, course_id: str, chapter_id: str = "", max_id: int = 0,
                                 max_order_num: int = 0, reverse: bool = False):
                assert reverse is True
                # 模拟真实接口行为：max_order_num 为“严格小于”边界
                if max_order_num > 0:
                    candidates = [x for x in self._items if x["order_num"] < max_order_num]
                else:
                    candidates = list(self._items)

                candidates.sort(key=lambda x: x["order_num"], reverse=True)
                return candidates[:30]

        client = FakeDedaoClient()
        articles = client.get_all_articles("course-1")
        orders = sorted([a.get("order_num", 0) for a in articles])

        assert len(articles) == 32
        assert orders[0] == 1
        assert orders[-1] == 32
        assert 2 in orders
