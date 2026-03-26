#!/usr/bin/env python3
"""Batch download courses listed in a markdown manifest."""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dedao import DedaoAPIError, DedaoClient
from dedao.downloader import CourseDownloader
from utils import get_config, load_config

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def load_cookie() -> str:
    config_path = Path.home() / ".dedao-notebooklm" / "config.json"
    if not config_path.exists():
        return ""
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data.get("dedao_cookie", "")
    except Exception as exc:
        logger.error("读取配置失败: %s", exc)
        return ""


def parse_course_list(file_path: Path) -> list[dict[str, str]]:
    content = file_path.read_text(encoding="utf-8")
    pattern = r"ID:\s*([A-Za-z0-9]+)\s*\n标题[：:]\s*(.+?)(?:\n|$)"
    matches = re.findall(pattern, content)
    return [{"id": course_id, "title": title.strip()} for course_id, title in matches]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量下载课程清单中的课程")
    parser.add_argument(
        "--list-file",
        default=str(REPO_ROOT / "test_downloads" / "我的专栏课程清单.md"),
        help="课程清单 Markdown 文件",
    )
    parser.add_argument("--output", default="", help="输出目录；默认使用配置中的 download_dir")
    parser.add_argument("--workers", type=int, default=5, help="并发数")
    parser.add_argument("--sleep-seconds", type=float, default=2.0, help="课程之间的等待秒数")
    return parser.parse_args()


def main() -> int:
    load_config()
    args = parse_args()
    cookie = load_cookie()
    if not cookie:
        print("错误：请先登录（dedao-nb login）")
        return 1

    list_file = Path(args.list_file).expanduser().resolve()
    if not list_file.exists():
        print(f"错误：找不到课程清单文件 {list_file}")
        return 1

    courses = parse_course_list(list_file)
    if not courses:
        print("错误：课程清单为空或格式不匹配")
        return 1

    output_dir = Path(args.output) if args.output else Path(get_config().download_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = DedaoClient(cookie)
    downloader = CourseDownloader(client, max_workers=args.workers, output_dir=output_dir)

    success_count = 0
    fail_count = 0
    failed_courses: list[str] = []

    print(f"共找到 {len(courses)} 个课程")
    for index, course in enumerate(courses, start=1):
        course_id = course["id"]
        title = course["title"]
        print(f"\n[{index}/{len(courses)}] 下载: {title}")
        print(f"ID: {course_id}")
        try:
            results = downloader.download_course(course_id, include_audio=False)
            chapter_success = sum(1 for result in results if result.success)
            if chapter_success > 0:
                success_count += 1
                print(f"成功: {chapter_success}/{len(results)} 章节")
            else:
                fail_count += 1
                failed_courses.append(f"{title} ({course_id})")
                print("失败: 未下载到任何章节")
        except DedaoAPIError as exc:
            fail_count += 1
            failed_courses.append(f"{title} ({course_id})")
            print(f"失败: {exc}")
        except Exception as exc:
            fail_count += 1
            failed_courses.append(f"{title} ({course_id})")
            print(f"异常: {exc}")

        if index < len(courses):
            time.sleep(args.sleep_seconds)

    print("\n下载完成")
    print(f"成功: {success_count}/{len(courses)}")
    print(f"失败: {fail_count}/{len(courses)}")
    if failed_courses:
        print("失败课程:")
        for item in failed_courses:
            print(f"- {item}")
    print(f"输出目录: {output_dir}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
