#!/usr/bin/env python3
"""创建 NotebookLM 笔记本并上传课程文件

用法：
  python create_and_upload.py <课程名称> [课程目录]

示例：
  python create_and_upload.py "30天认知训练营第三季" downloads/30天认知训练营第三季
"""

import sys
import time
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main():
    # 解析参数
    if len(sys.argv) < 2:
        print("用法: python create_and_upload.py <课程名称> [课程目录]")
        print()
        print("示例:")
        print('  python create_and_upload.py "30天认知训练营第三季"')
        print('  python create_and_upload.py "30天认知训练营第三季" downloads/30天认知训练营第三季')
        return False

    course_title = sys.argv[1]

    # 确定课程目录
    if len(sys.argv) >= 3:
        course_dir = Path(sys.argv[2])
    else:
        # 默认在 downloads 目录下查找同名目录
        course_dir = Path(__file__).parent / "downloads" / course_title

    # 检查目录
    if not course_dir.exists():
        print(f"错误：目录不存在 - {course_dir}")
        return False

    # 查找 MD 文件
    md_files = sorted(course_dir.glob("*.md"))
    if not md_files:
        print(f"错误：未找到 Markdown 文件 - {course_dir}")
        return False

    print(f"课程名称: {course_title}")
    print(f"课程目录: {course_dir}")
    print(f"文件数量: {len(md_files)} 个")
    print()

    # 导入模块
    from notebooklm.browser import NotebookLMBrowser, NotebookLibrary

    browser = None
    try:
        # 启动浏览器（非无头模式，方便首次登录）
        print("正在启动浏览器...")
        browser = NotebookLMBrowser(headless=False)

        # 检查认证状态
        print("检查登录状态...")
        if not browser.is_authenticated():
            print()
            print("请先登录 Google 账户：")
            print("1. 在打开的浏览器中登录 Google")
            print("2. 登录成功后脚本会继续执行")
            print()
            # 等待用户登录
            time.sleep(5)

            # 再次检查
            if not browser.is_authenticated():
                print("仍未检测到登录，请手动登录后重试")
                return False

        print("已登录！")
        print()

        # 创建 Notebook
        print(f"创建 Notebook: {course_title}")
        notebook_info = browser.create_notebook(course_title, debug=True)

        if not notebook_info:
            print("错误：创建 Notebook 失败")
            return False

        print(f"Notebook ID: {notebook_info.id}")
        print(f"Notebook URL: {notebook_info.url}")
        print()

        # 保存 Notebook 信息
        library = NotebookLibrary()
        library.add_notebook(
            notebook_id=notebook_info.id,
            title=course_title,
            url=notebook_info.url
        )
        print(f"已保存 Notebook 信息到本地库")
        print()

        # 上传文件
        print(f"开始上传 {len(md_files)} 个文件...")
        success_count = 0

        for i, file_path in enumerate(md_files, 1):
            print(f"  [{i}/{len(md_files)}] 上传: {file_path.name}")

            if browser.upload_file(file_path):
                success_count += 1
                print(f"              ✓ 成功")
            else:
                print(f"              ✗ 失败")

            # 等待一下，避免上传太快
            time.sleep(2)

        print()
        print(f"上传完成：{success_count}/{len(md_files)} 成功")
        print(f"Notebook URL: {notebook_info.url}")
        print()
        print("Notebook ID 已保存，下次可以直接使用 upload_to_notebooklm.py 上传")

        return success_count == len(md_files)

    except Exception as e:
        print(f"错误：{e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if browser:
            print()
            print("等待 5 秒后关闭浏览器...")
            time.sleep(5)
            browser.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
