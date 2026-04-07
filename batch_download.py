#!/usr/bin/env python3
"""批量下载清单中的所有专栏课程"""

import sys
import re
import json
import time
import logging
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dedao import DedaoClient, DedaoAPIError
from dedao.downloader import CourseDownloader

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_cookie() -> str:
    """从配置文件加载 cookie"""
    config_path = Path.home() / ".dedao-notebooklm" / "config.json"
    if not config_path.exists():
        return ""
    try:
        data = json.loads(config_path.read_text(encoding='utf-8'))
        return data.get('dedao_cookie', '')
    except Exception as e:
        logger.error(f"读取配置失败：{e}")
        return ""


def parse_course_list(file_path: str) -> list:
    """解析课程清单文件，提取课程ID和标题"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    courses = []
    # 匹配模式：ID: xxx  标题：xxx
    pattern = r'ID:\s*([A-Za-z0-9]+)\s*\n标题[：:]\s*(.+?)(?:\n|$)'
    matches = re.findall(pattern, content)

    for course_id, title in matches:
        courses.append({
            'id': course_id,
            'title': title.strip()
        })

    return courses


def main():
    # 加载 cookie
    cookie = load_cookie()
    if not cookie:
        print("错误：请先登录 (dedao-nb login)")
        return

    # 解析课程清单
    list_file = Path(__file__).parent / "test_downloads" / "我的专栏课程清单.md"
    if not list_file.exists():
        print(f"错误：找不到课程清单文件 {list_file}")
        return

    courses = parse_course_list(str(list_file))
    print(f"共找到 {len(courses)} 个课程")

    # 输出目录
    output_dir = Path("./downloads")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 初始化客户端
    client = DedaoClient(cookie)
    downloader = CourseDownloader(
        client,
        max_workers=5,
        output_dir=output_dir
    )

    # 统计
    success_count = 0
    fail_count = 0
    failed_courses = []

    # 逐个下载课程
    for i, course in enumerate(courses, 1):
        course_id = course['id']
        title = course['title']

        print(f"\n{'='*60}")
        print(f"[{i}/{len(courses)}] 下载：{title}")
        print(f"ID: {course_id}")
        print(f"{'='*60}")

        try:
            results = downloader.download_course(course_id, include_audio=False)

            # 检查下载结果
            chapter_success = sum(1 for r in results if r.success)
            chapter_total = len(results)

            if chapter_success > 0:
                print(f"✓ 下载成功：{chapter_success}/{chapter_total} 章节")
                success_count += 1
            else:
                print(f"✗ 下载失败：0 章节")
                fail_count += 1
                failed_courses.append(f"{title} ({course_id})")

        except DedaoAPIError as e:
            print(f"✗ 下载失败：{e}")
            fail_count += 1
            failed_courses.append(f"{title} ({course_id})")
        except Exception as e:
            print(f"✗ 下载出错：{e}")
            fail_count += 1
            failed_courses.append(f"{title} ({course_id})")

        # 避免请求过于频繁
        if i < len(courses):
            time.sleep(2)

    # 打印汇总
    print(f"\n{'='*60}")
    print("下载完成汇总")
    print(f"{'='*60}")
    print(f"成功：{success_count}/{len(courses)}")
    print(f"失败：{fail_count}/{len(courses)}")

    if failed_courses:
        print("\n失败的课程：")
        for c in failed_courses:
            print(f"  - {c}")

    print(f"\n文件保存位置：{output_dir}")


if __name__ == "__main__":
    main()
