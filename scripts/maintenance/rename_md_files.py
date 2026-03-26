#!/usr/bin/env python3
"""Rename markdown files by extracting their first-level heading."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from utils import get_config, load_config


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name)


def extract_title(file_path: Path) -> str | None:
    try:
        first_line = file_path.read_text(encoding="utf-8").splitlines()[0].strip()
    except Exception:
        return None
    if first_line.startswith("#"):
        return first_line.lstrip("#").strip()
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按一级标题批量重命名 Markdown 文件")
    parser.add_argument("--target-dir", default="", help="目标目录；默认使用配置中的 download_dir")
    return parser.parse_args()


def main() -> int:
    load_config()
    args = parse_args()
    target_dir = Path(args.target_dir) if args.target_dir else Path(get_config().download_dir)
    target_dir = target_dir.expanduser().resolve()

    if not target_dir.exists():
        print(f"错误：目录不存在 - {target_dir}")
        return 1

    total_success = 0
    total_skip = 0
    total_error = 0

    for folder in sorted(target_dir.iterdir()):
        if not folder.is_dir():
            continue
        print(f"\n处理文件夹: {folder.name}")
        for path in sorted(folder.glob("*.md")):
            title = extract_title(path)
            if not title:
                total_skip += 1
                continue

            new_name = sanitize_filename(title) + ".md"
            new_path = path.with_name(new_name)
            if path.name == new_name or new_path.exists():
                total_skip += 1
                continue

            try:
                path.rename(new_path)
                print(f"[成功] {new_name}")
                total_success += 1
            except Exception as exc:
                print(f"[失败] {path.name}: {exc}")
                total_error += 1

    print(f"\n完成。成功: {total_success}，跳过: {total_skip}，失败: {total_error}")
    return 0 if total_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
