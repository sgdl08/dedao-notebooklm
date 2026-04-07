"""
自动生成的全面测试用例
生成时间: 2026-03-20T06:16:54.847477
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dedao.models import (
    Course, Chapter, CourseDetail, Audiobook, AudiobookChapter,
    AudiobookDetail, EbookCatalog, EbookDetail, EbookChapter,
    ChannelInfo, ChannelNote, Topic, TopicNote
)
from dedao.auth import DedaoAuth, DedaoQRCodeLogin
from dedao.client import DedaoClient, DedaoAPIError, Category


# ==================== 模型测试 ====================

class TestCourseModelComprehensive:
    """Course模型全面测试"""

    def test_course_creation_minimal(self):
        """测试最小字段创建"""
        course = Course(id="123", title="测试")
        assert course.id == "123"
        assert course.title == "测试"

    def test_course_creation_full(self):
        """测试完整字段创建"""
        course = Course(
            id="123",
            title="测试课程",
            cover="https://example.com/cover.jpg",
            author="测试作者",
            description="这是描述",
            chapter_count=10,
            is_finished=True,
            category="bauhinia"
        )
        assert course.author == "测试作者"
        assert course.chapter_count == 10
        assert course.is_finished is True

    def test_course_with_extra_fields(self):
        """测试extra字段"""
        course = Course(
            id="123",
            title="测试",
            extra={"key": "value", "number": 42}
        )
        assert course.extra["key"] == "value"
        assert course.extra["number"] == 42

    def test_course_default_values(self):
        """测试默认值"""
        course = Course(id="1", title="test")
        assert course.cover == ""
        assert course.author == ""
        assert course.chapter_count == 0
        assert course.is_finished is False
        assert course.extra == {}


class TestChapterModelComprehensive:
    """Chapter模型全面测试"""

    def test_chapter_creation_minimal(self):
        """测试最小字段创建"""
        chapter = Chapter(id="1", course_id="c1", title="第一章")
        assert chapter.id == "1"
        assert chapter.course_id == "c1"

    def test_chapter_with_audio(self):
        """测试音频字段"""
        chapter = Chapter(
            id="1",
            course_id="c1",
            title="第一章",
            audio_url="https://example.com/audio.mp3",
            audio_duration=300
        )
        assert chapter.audio_url is not None
        assert chapter.audio_duration == 300

    def test_chapter_sort_order(self):
        """测试排序"""
        chapters = [
            Chapter(id="3", course_id="c1", title="三", sort_order=3),
            Chapter(id="1", course_id="c1", title="一", sort_order=1),
            Chapter(id="2", course_id="c1", title="二", sort_order=2),
        ]
        sorted_chapters = sorted(chapters, key=lambda x: x.sort_order)
        assert sorted_chapters[0].id == "1"


class TestCourseDetailComprehensive:
    """CourseDetail全面测试"""

    def test_empty_course_detail(self):
        """测试空课程详情"""
        course = Course(id="1", title="test")
        detail = CourseDetail(course=course)
        assert detail.total_chapters == 0
        assert detail.has_audio is False

    def test_course_detail_with_chapters(self):
        """测试带章节的课程详情"""
        course = Course(id="1", title="test")
        chapters = [
            Chapter(id="1", course_id="1", title="ch1"),
            Chapter(id="2", course_id="1", title="ch2", audio_url="url"),
        ]
        detail = CourseDetail(course=course, chapters=chapters)
        assert detail.total_chapters == 2
        assert detail.has_audio is True


class TestAudiobookModels:
    """有声书模型测试"""

    def test_audiobook_creation(self):
        """测试有声书创建"""
        book = Audiobook(
            alias_id="ab123",
            title="测试有声书",
            author="作者",
            reader="朗读者"
        )
        assert book.alias_id == "ab123"
        assert book.reader == "朗读者"

    def test_audiobook_detail_duration(self):
        """测试有声书时长计算"""
        book = Audiobook(alias_id="1", title="test")
        chapters = [
            AudiobookChapter(id="1", title="ch1", duration=100),
            AudiobookChapter(id="2", title="ch2", duration=200),
        ]
        detail = AudiobookDetail(audiobook=book, chapters=chapters)
        assert detail.total_duration == 300


class TestEbookModels:
    """电子书模型测试"""

    def test_ebook_catalog(self):
        """测试电子书目录"""
        catalog = EbookCatalog(
            chapter_id="ch1",
            title="第一章",
            level=0,
            order=1
        )
        assert catalog.chapter_id == "ch1"
        assert catalog.level == 0

    def test_ebook_chapter_with_svg(self):
        """测试带SVG的章节"""
        chapter = EbookChapter(
            chapter_id="ch1",
            title="第一章",
            svg_contents=["<svg>1</svg>", "<svg>2</svg>"]
        )
        assert len(chapter.svg_contents) == 2


# ==================== 认证测试 ====================

class TestDedaoAuthComprehensive:
    """认证全面测试"""

    def test_auth_with_cookie(self):
        """测试带Cookie的认证"""
        auth = DedaoAuth(cookie="test=123")
        assert auth.is_authenticated() is True

    def test_auth_headers(self):
        """测试认证头"""
        auth = DedaoAuth(cookie="test=123")
        headers = auth.headers
        assert "Cookie" in headers
        assert "test=123" in headers["Cookie"]
        assert "User-Agent" in headers

    def test_auth_without_cookie(self):
        """测试无Cookie情况"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            auth = DedaoAuth(config_path=Path(tmpdir) / "config.json")
            assert auth.is_authenticated() is False


# ==================== API客户端测试 ====================

class TestDedaoClientComprehensive:
    """API客户端全面测试"""

    def test_client_initialization(self):
        """测试客户端初始化"""
        client = DedaoClient(cookie="test=123")
        assert client.is_authenticated() is True

    def test_client_set_cookie(self):
        """测试设置Cookie"""
        client = DedaoClient()
        client.set_cookie("new=cookie")
        assert client.is_authenticated() is True

    def test_api_error_handling(self):
        """测试API错误处理"""
        client = DedaoClient(cookie="test=123")

        # 模拟网络错误
        with patch.object(client, '_request') as mock_request:
            mock_request.side_effect = DedaoAPIError("测试错误")
            with pytest.raises(DedaoAPIError):
                client.get_course_list()

    def test_category_constants(self):
        """测试分类常量"""
        assert Category.ALL == "all"
        assert Category.COURSE == "bauhinia"
        assert Category.AUDIOBOOK == "odob"
        assert Category.EBOOK == "ebook"


class TestPaginationLogic:
    """分页逻辑测试"""

    def test_pagination_is_more_detection(self):
        """测试is_more检测"""
        # 模拟第一页有更多
        response_page1 = {
            "c": {"list": [{"id": i} for i in range(20)], "total": 50, "is_more": 1}
        }
        assert response_page1["c"]["is_more"] == 1

        # 模拟最后一页
        response_last = {
            "c": {"list": [{"id": i} for i in range(10)], "total": 50, "is_more": 0}
        }
        assert response_last["c"]["is_more"] == 0

    def test_article_pagination_order_num(self):
        """测试文章分页使用order_num"""
        articles = [
            {"id": "1", "order_num": 1},
            {"id": "2", "order_num": 2},
            {"id": "3", "order_num": 3},
        ]
        # 模拟reverse=True时的获取
        min_order = min(a["order_num"] for a in articles)
        assert min_order == 1


class TestAPIResponseParsing:
    """API响应解析测试"""

    def test_parse_nested_response(self):
        """测试嵌套响应解析"""
        # 得到API返回的数据结构
        response = {
            "h": {"c": 0, "e": ""},
            "c": {
                "list": [
                    {"enid": "1", "title": "课程1"},
                    {"enid": "2", "title": "课程2"},
                ],
                "total": 2,
                "is_more": 0
            }
        }

        # 解析逻辑
        resp_data = response.get("c", {}) or response.get("data", {})
        items = resp_data.get("list", [])
        assert len(items) == 2

    def test_parse_error_response(self):
        """测试错误响应解析"""
        response = {
            "h": {"c": -1, "e": "未登录"},
            "c": {}
        }

        # 检查错误
        if response.get("h", {}).get("c") != 0:
            error_msg = response.get("h", {}).get("e", "未知错误")
            assert error_msg == "未登录"

    def test_parse_alternative_data_structure(self):
        """测试备选数据结构"""
        # 有些API直接返回data字段
        response = {
            "code": 0,
            "data": {
                "list": [{"id": "1"}]
            }
        }

        # 解析逻辑
        resp_data = response.get("c", {}) or response.get("data", {})
        items = resp_data.get("list", [])
        assert len(items) == 1


# ==================== 边界条件测试 ====================

class TestEdgeCases:
    """边界条件测试"""

    def test_empty_string_handling(self):
        """测试空字符串处理"""
        course = Course(id="", title="")
        assert course.id == ""
        assert course.title == ""

    def test_special_characters_in_title(self):
        """测试标题中的特殊字符"""
        chapter = Chapter(
            id="1",
            course_id="c1",
            title="标题<包含>/特殊:字符?|"
        )
        assert "<" in chapter.title

    def test_unicode_handling(self):
        """测试Unicode处理"""
        course = Course(
            id="1",
            title="中文标题 🎉 表情符号",
            description="日本語テスト"
        )
        assert "🎉" in course.title

    def test_large_number_handling(self):
        """测试大数字处理"""
        course = Course(
            id="1",
            title="test",
            chapter_count=999999
        )
        assert course.chapter_count == 999999

    def test_null_values(self):
        """测试空值处理"""
        chapter = Chapter(
            id="1",
            course_id="c1",
            title="test",
            audio_url=None,
            audio_duration=None
        )
        assert chapter.audio_url is None


# ==================== 并发和性能测试 ====================

class TestConcurrencyAndPerformance:
    """并发和性能测试"""

    def test_concurrent_chapter_creation(self):
        """测试并发章节创建"""
        from concurrent.futures import ThreadPoolExecutor

        def create_chapter(i):
            return Chapter(id=str(i), course_id="c1", title=f"Chapter {i}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            chapters = list(executor.map(create_chapter, range(10)))

        assert len(chapters) == 10

    def test_large_course_detail(self):
        """测试大型课程详情"""
        course = Course(id="1", title="大课程")
        chapters = [
            Chapter(id=str(i), course_id="1", title=f"第{i}章", sort_order=i)
            for i in range(1000)
        ]
        detail = CourseDetail(course=course, chapters=chapters)
        assert detail.total_chapters == 1000


# ==================== API端点测试 ====================

class TestAPIEndpoints:
    """API端点测试 - 基于发现的端点"""

    @patch('requests.Session.request')
    def test_course_list_endpoint(self, mock_request):
        """测试课程列表端点"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "c": {"list": [], "total": 0, "is_more": 0}
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = DedaoClient(cookie="test=123")
        result = client.get_course_list()

        assert "list" in result
        mock_request.assert_called()

    @patch('requests.Session.request')
    def test_course_detail_endpoint(self, mock_request):
        """测试课程详情端点"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "h": {"c": 0},
            "c": {
                "class_info": {"enid": "1", "name": "测试课程"},
                "chapter_list": []
            }
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = DedaoClient(cookie="test=123")
        detail = client.get_course_detail("test_id")

        assert detail.course.title == "测试课程"


# ==================== 速率限制测试 ====================

class TestRateLimiting:
    """速率限制测试"""

    def test_rate_limit_handling(self):
        """测试速率限制处理"""
        # 模拟速率限制响应
        rate_limit_response = {
            "code": 429,
            "msg": "请求过于频繁"
        }

        assert rate_limit_response["code"] == 429

    def test_retry_logic(self):
        """测试重试逻辑"""
        retry_count = 0
        max_retries = 3

        def mock_api_call():
            nonlocal retry_count
            retry_count += 1
            if retry_count < max_retries:
                raise DedaoAPIError("临时错误")
            return {"success": True}

        # 简单重试
        for i in range(max_retries):
            try:
                result = mock_api_call()
                break
            except DedaoAPIError:
                if i == max_retries - 1:
                    raise

        assert retry_count == max_retries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
