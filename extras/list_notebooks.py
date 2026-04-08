#!/usr/bin/env python3
"""列出 NotebookLM 笔记本清单并保存到本地 Markdown 文件

用法：
  python list_notebooks.py [-o output.md]

此脚本会：
1. 使用浏览器自动化访问 NotebookLM
2. 获取笔记本列表
3. 保存为 Markdown 格式
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / "src"))

from notebooklm import NotebookLMBrowser, EnhancedNotebookLibrary


def main():
    import argparse

    parser = argparse.ArgumentParser(description="列出 NotebookLM 笔记本清单")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("notebooks_list.md"),
        help="输出 Markdown 文件路径"
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="显示浏览器窗口"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("NotebookLM 笔记本清单")
    print("=" * 60)
    print()

    browser = None
    try:
        # 启动浏览器
        print("启动浏览器...")
        browser = NotebookLMBrowser(headless=not args.headful)
        browser._ensure_browser()

        # 讣问 NotebookLM 首页
        print("访问 NotebookLM...")
        browser._page.goto("https://notebooklm.google.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # 获取笔记本列表
        print("获取笔记本列表...")

        # NotebookLM 首页的笔记本列表元素
        notebook_selectors = [
            '[data-notebook-id]',
            '[data-notebook-id]',
            'a[href*="/notebook/"]',
            '.notebook-card',
            '.notebook-item',
            '[class*="notebook"]',
        ]

        notebooks = []
        for selector in notebook_selectors:
            try:
                elements = browser._page.query_selector_all(selector)
                if elements:
                    for elem in elements:
                        try:
                            notebook_id = elem.get_attribute('data-notebook-id')
                            href = elem.get_attribute('href')
                            title = elem.inner_text().strip()

                            if notebook_id or href:
                                notebooks.append({
                                    'id': notebook_id or (href.split('/')[-1] if href else 'unknown'),
                                    'title': title,
                                    'url': f"https://notebooklm.google.com{href}" if href.startswith('/') else href if href else None
                                })
                        except:
                            continue
                    if notebooks:
                        break
            except:
                continue

        # 如果没找到，尝试从本地库获取
        if not notebooks:
            print("从本地库获取笔记本列表...")
            library = EnhancedNotebookLibrary()
            local_notebooks = library.list_notebooks()
            for nb in local_notebooks:
                notebooks.append({
                    'id': nb.id,
                    'title': nb.name or nb.title,
                    'url': nb.url,
                    'source_count': nb.source_count,
                    'last_used': nb.last_used,
                })

        # 保存为 Markdown
        output_lines = [
            "# NotebookLM 笔记本清单",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "| 笔记本 ID | 名称 | 源文件数 | 最后使用 | URL |",
            "|:--------|:-----|:---------|:---------|:---|",
        ]

        for nb in notebooks:
            notebook_id = nb.get('id', 'N/A')
            title = nb.get('title', '未命名')
            source_count = nb.get('source_count', 0)
            last_used = nb.get('last_used', 'N/A')
            url = nb.get('url', 'N/A')

            output_lines.append(
                f"| `{notebook_id}` | {title} | {source_count} | {last_used} | {url} |"
            )

        output_lines.append("")
        output_lines.append(f"**共 {len(notebooks)} 个笔记本**")

        # 写入文件
        args.output.write_text("\n".join(output_lines), encoding='utf-8')
        print()
        print(f"✓ 已保存到: {args.output}")
        print()

        # 打印内容
        for line in output_lines:
                print(line)

        return True

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        if browser:
            print()
            print("等待 3 秒后关闭浏览器...")
            time.sleep(3)
            browser.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
