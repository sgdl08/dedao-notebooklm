#!/usr/bin/env python3
"""上传文件到当前打开的 NotebookLM 笔记本

用法：
  python upload_files.py <课程目录或文件>
  python upload_files.py downloads/30天认知训练营第三季/*.md

此脚本会上传文件到浏览器中当前打开的笔记本。
"""

import sys
import time
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main():
    if len(sys.argv) < 2:
        print("用法: python upload_files.py <文件或目录>")
        print()
        print("示例:")
        print("  python upload_files.py downloads/30天认知训练营第三季")
        print("  python upload_files.py downloads/30天认知训练营第三季/*.md")
        return False

    # 收集文件
    files = []
    for arg in sys.argv[1:]:
        path = Path(arg)
        if path.is_dir():
            files.extend(sorted(path.glob("*.md")))
        elif path.exists():
            files.append(path)

    if not files:
        print("错误：未找到文件")
        return False

    print(f"准备上传 {len(files)} 个文件")
    print()

    from notebooklm.browser import NotebookLMBrowser

    browser = None
    try:
        print("启动浏览器（使用已保存的会话）...")
        browser = NotebookLMBrowser(headless=False)

        # 检查当前页面
        browser._ensure_browser()
        current_url = browser._page.url
        print(f"当前页面: {current_url}")

        if "notebooklm.google.com" not in current_url:
            print("请先在浏览器中打开 NotebookLM 笔记本页面")
            print("然后再次运行此脚本")
            return False

        # 上传文件
        print(f"\n开始上传 {len(files)} 个文件...")
        success_count = 0

        for i, file_path in enumerate(files, 1):
            print(f"  [{i}/{len(files)}] {file_path.name}")

            if browser.upload_file(file_path):
                success_count += 1
                print(f"              ✓ 成功")
            else:
                print(f"              ✗ 失败")

            time.sleep(2)  # 避免上传太快

        print()
        print(f"上传完成：{success_count}/{len(files)} 成功")

        return success_count == len(files)

    except Exception as e:
        print(f"错误：{e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if browser:
            print("\n等待 5 秒后关闭浏览器...")
            time.sleep(5)
            browser.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
