#!/usr/bin/env python3
"""Redownload a fixed list of courses into the configured external data directory."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dedao import DedaoClient
from dedao.downloader import CourseDownloader
from utils import get_config, load_config

COURSES_TO_FIX = [
    ("z1DWOMARavZVxoMsnxKP2mlx7bjydL", "罗胖60秒·十年合集"),
    ("v12pOMZN7mbJwgMsNyJDrjxdYaGkoE", "宁向东的管理学课"),
    ("lrW8nAoE2ZNJl1aHxyXQRy0OazeGPw", "万维钢·精英日课"),
    ("jvwNqE9ZL10K4E0snkVG7Pp8mDnRWo", "吴军来信2"),
    ("9LnlWEqDj76VzmMsM0KmOA4epMBPxa", "万维钢·精英日课"),
    ("YE36g8pDr7WJoQas82KP4Z5Rlwjy0z", "万维钢·精英日课"),
    ("93N5e6Rya4ZJjQYsQgVOmGApwlo08D", "万维钢·精英日课"),
    ("7A5gvRBmGlWVGdqsDOJZLpj9Mnow63", "万维钢·精英日课"),
    ("9emjk1LQqzoK25LhYvX2lbY6Pv0BDW", "万维钢·精英日课"),
    ("lQr3o4dMw8ZKgdasgrV7N2xDyWeEq1", "5分钟商学院·基础"),
    ("PZNRwQ0qL1MVEbAskxJ3lmz4kgWEnx", "硅谷来信2·谷歌方法论"),
    ("qBr4kj5gLNYKNdPsm2JdemExy36GaA", "听书番外篇"),
]


def main() -> int:
    load_config()
    config_path = Path.home() / ".dedao-notebooklm" / "config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    cookie = data.get("dedao_cookie", "")
    if not cookie:
        print("错误：未配置 dedao_cookie")
        return 1

    output_dir = Path(get_config().download_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = DedaoClient(cookie)
    downloader = CourseDownloader(client, max_workers=5, output_dir=output_dir)

    print(f"将重新下载 {len(COURSES_TO_FIX)} 个课程")
    for index, (course_id, title) in enumerate(COURSES_TO_FIX, start=1):
        print(f"\n[{index}/{len(COURSES_TO_FIX)}] 重新下载: {title}")
        old_dir = output_dir / title
        if old_dir.exists():
            shutil.rmtree(old_dir)
            print("已删除旧目录")

        try:
            results = downloader.download_course(course_id, include_audio=False)
            success = sum(1 for result in results if result.success)
            print(f"完成: {success}/{len(results)} 章节")
        except Exception as exc:
            print(f"失败: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
