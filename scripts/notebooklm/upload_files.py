#!/usr/bin/env python3
"""上传文件到 NotebookLM 笔记本。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from notebooklm.browser import NotebookLMBrowser
from notebooklm.library import EnhancedNotebookLibrary


def collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for arg in paths:
        path = Path(arg)
        if path.is_dir():
            files.extend(sorted(path.glob("*.md")))
            continue
        if path.exists():
            files.append(path)
    return files


def resolve_notebook_id(explicit: str) -> str:
    if explicit:
        return explicit
    library = EnhancedNotebookLibrary()
    active_id = library.get_active_notebook_id()
    return active_id or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="上传文件到 NotebookLM")
    parser.add_argument("inputs", nargs="+", help="文件或目录路径")
    parser.add_argument("--notebook-id", default="", help="目标笔记本 ID（默认使用本地 active notebook）")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口")
    args = parser.parse_args()

    files = collect_files(args.inputs)
    if not files:
        print("错误：未找到可上传文件")
        return 1

    notebook_id = resolve_notebook_id(args.notebook_id)
    if not notebook_id:
        print("错误：未提供 --notebook-id 且本地无 active notebook")
        return 1

    browser = NotebookLMBrowser(headless=not args.headful)
    try:
        browser.set_active_notebook(notebook_id)
        stats = browser.upload_files(files)
    except Exception as e:
        print(f"错误：{e}")
        return 1
    finally:
        browser.close()

    print(f"Notebook ID: {notebook_id}")
    print(f"上传结果: {stats['success']}/{stats['total']} 成功")
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
