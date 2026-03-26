"""课程同步流程测试。"""

import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from course_sync import CourseSyncService
from dedao.models import Chapter, Course, CourseDetail


class FakeClient:
    def get_course_detail(self, course_id: str) -> CourseDetail:
        course = Course(id=course_id, title="测试课程")
        chapters = [
            Chapter(id="ch1", course_id=course_id, title="第一章", sort_order=1),
            Chapter(id="ch2", course_id=course_id, title="第二章", sort_order=2),
        ]
        return CourseDetail(course=course, chapters=chapters)

    def get_chapter_content(self, chapter_id: str) -> Chapter:
        title_map = {"ch1": "第一章", "ch2": "第二章"}
        order_map = {"ch1": 1, "ch2": 2}
        return Chapter(
            id=chapter_id,
            course_id="course-1",
            title=title_map[chapter_id],
            sort_order=order_map[chapter_id],
            content=f"# {title_map[chapter_id]}\n\n这是 {chapter_id} 的内容。",
            audio_url="",
        )

    def download_file(self, url: str, save_path: Path) -> Path:
        save_path.write_bytes(b"")
        return save_path


def test_sync_course_generates_manifest_and_state(tmp_path: Path):
    service = CourseSyncService(
        client=FakeClient(),
        output_root=tmp_path,
        workers=2,
    )

    result = service.sync_course(
        course_id="course-1",
        include_audio=False,
        output_format="md",
        upload_to_notebooklm=False,
    )

    assert result.downloaded == 2
    assert result.failed == 0
    assert result.manifest_path.exists()
    assert result.chapter_state_path.exists()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "v1"
    assert manifest["course_id"] == "course-1"
    assert manifest["downloaded"] == 2

    chapter_state = json.loads(result.chapter_state_path.read_text(encoding="utf-8"))
    assert "ch1" in chapter_state
    assert chapter_state["ch1"]["status"] == "completed"
