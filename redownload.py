#!/usr/bin/env python3
"""重新下载不完整的课程"""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dedao import DedaoClient
from dedao.downloader import CourseDownloader

# 需要重新下载的课程（ID, 标题）
COURSES_TO_FIX = [
    ("z1DWOMARavZVxoMsnxKP2mlx7bjydL", "罗胖60秒·十年合集"),
    ("v12pOMZN7mbJwgMsNyJDrjxdYaGkoE", "宁向东的管理学课"),
    ("lrW8nAoE2ZNJl1aHxyXQRy0OazeGPw", "万维钢·精英日课6"),
    ("jvwNqE9ZL10K4E0snkVG7Pp8mDnRWo", "吴军来信2"),
    ("9LnlWEqDj76VzmMsM0KmOA4epMBPxa", "万维钢·精英日课4"),
    ("YE36g8pDr7WJoQas82KP4Z5Rlwjy0z", "万维钢·精英日课5"),
    ("93N5e6Rya4ZJjQYsQgVOmGApwlo08D", "万维钢·精英日课"),
    ("7A5gvRBmGlWVGdqsDOJZLpj9Mnow63", "万维钢·精英日课3"),
    ("9emjk1LQqzoK25LhYvX2lbY6Pv0BDW", "万维钢·精英日课2"),
    ("lQr3o4dMw8ZKgdasgrV7N2xDyWeEq1", "5分钟商学院·基础"),
    ("PZNRwQ0qL1MVEbAskxJ3lmz4kgWEnx", "硅谷来信2·谷歌方法论"),
    ("qBr4kj5gLNYKNdPsm2JdemExy36GaA", "听书番外篇"),
]

def main():
    config_path = Path.home() / ".dedao-notebooklm" / "config.json"
    data = json.loads(config_path.read_text(encoding='utf-8'))
    cookie = data.get('dedao_cookie', '')
    
    output_dir = Path("./downloads")
    client = DedaoClient(cookie)
    downloader = CourseDownloader(client, max_workers=5, output_dir=output_dir)
    
    print(f"将重新下载 {len(COURSES_TO_FIX)} 个课程")
    
    for i, (course_id, title) in enumerate(COURSES_TO_FIX, 1):
        print(f"\n[{i}/{len(COURSES_TO_FIX)}] 重新下载: {title}")
        
        # 删除旧目录
        old_dir = output_dir / title
        if old_dir.exists():
            import shutil
            shutil.rmtree(old_dir)
            print(f"  已删除旧目录")
        
        try:
            results = downloader.download_course(course_id, include_audio=False)
            success = sum(1 for r in results if r.success)
            print(f"  ✓ 下载完成: {success}/{len(results)} 章节")
        except Exception as e:
            print(f"  ✗ 下载失败: {e}")

if __name__ == "__main__":
    main()
