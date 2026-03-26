#!/usr/bin/env python3
"""Create a NotebookLM notebook and upload all markdown files from a course directory."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from notebooklm.browser import NotebookLMBrowser
from notebooklm.library import NotebookLibrary
from utils import get_config, load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建 NotebookLM 笔记本并上传课程 Markdown")
    parser.add_argument("course_title", help="Notebook 标题")
    parser.add_argument("course_dir", nargs="?", default="", help="课程目录；默认使用配置中的 download_dir/<课程名>")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口")
    return parser.parse_args()


def resolve_course_dir(course_title: str, explicit_dir: str) -> Path:
    if explicit_dir:
        return Path(explicit_dir).expanduser().resolve()
    return Path(get_config().download_dir).expanduser().resolve() / course_title


def main() -> int:
    load_config()
    args = parse_args()
    course_dir = resolve_course_dir(args.course_title, args.course_dir)

    if not course_dir.exists():
        print(f"错误：目录不存在 - {course_dir}")
        return 1

    md_files = sorted(course_dir.glob("*.md"))
    if not md_files:
        print(f"错误：未找到 Markdown 文件 - {course_dir}")
        return 1

    print(f"课程名称: {args.course_title}")
    print(f"课程目录: {course_dir}")
    print(f"文件数量: {len(md_files)}")

    browser = None
    try:
        browser = NotebookLMBrowser(headless=not args.headful)
        if not browser.is_authenticated():
            print("错误：当前 NotebookLM 未登录，请先完成登录。")
            return 1

        notebook_info = browser.create_notebook(args.course_title, debug=True)
        if not notebook_info:
            print("错误：创建 Notebook 失败")
            return 1

        NotebookLibrary().add_notebook(
            notebook_id=notebook_info.id,
            title=args.course_title,
            url=notebook_info.url,
        )

        success_count = 0
        for index, file_path in enumerate(md_files, start=1):
            print(f"[{index}/{len(md_files)}] 上传 {file_path.name}")
            if browser.upload_file(file_path):
                success_count += 1
            time.sleep(1)

        print(f"Notebook ID: {notebook_info.id}")
        print(f"Notebook URL: {notebook_info.url}")
        print(f"上传结果: {success_count}/{len(md_files)}")
        return 0 if success_count == len(md_files) else 1
    except Exception as exc:
        print(f"错误：{exc}")
        return 1
    finally:
        if browser:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
