#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 NotebookLM 网站获取笔记本列表并保存

用法：
  python3 fetch_notebooks.py [-o output.md] [--headful]

此脚本会：
1. 使用浏览器自动化访问 NotebookLM
2. 从页面获取笔记本列表
3. 同时更新本地库
4. 保存为 Markdown 格式
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

# 添加 src 到路径
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from notebooklm.browser import NotebookLMBrowser
from notebooklm.library import EnhancedNotebookLibrary
from notebooklm.api_client import NotebookLMAPIClient


def fetch_notebooks_from_api(browser):
    """使用 RPC API 获取笔记本列表 (优先方法)

    Args:
        browser: NotebookLMBrowser 实例 (用于获取 cookies)

    Returns:
        笔记本列表，失败返回空列表
    """
    try:
        print("[API] 正在使用 RPC API 获取笔记本列表...")

        # 从浏览器上下文获取 cookies
        context = browser._context
        if not context:
            print("[API] 无法获取浏览器上下文")
            return []

        # 创建 API 客户端
        client = NotebookLMAPIClient.from_playwright_context(context)
        notebooks = client.list_notebooks()
        client.close()

        if notebooks:
            print(f"[API] 成功获取 {len(notebooks)} 个笔记本")
            return [nb.to_dict() for nb in notebooks]
        else:
            print("[API] 未获取到笔记本，回退到 DOM 方式...")
            return []

    except Exception as e:
        print(f"[API] 获取失败: {e}，回退到 DOM 方式...")
        return []


def fetch_notebooks_from_dom(browser):
    """从 NotebookLM 网页获取笔记本列表 (DOM 选择器方式)

    Args:
        browser: NotebookLMBrowser 实例

    Returns:
        笔记本列表 (list of dict)
    """
    print("[DOM] 正在从页面获取笔记本列表...")

    # 等待页面加载
    time.sleep(3)

    # NotebookLM 首页的笔记本列表选择器
    notebook_selectors = [
        'a[href*="/notebook/"]',
        '[data-notebook-id]',
        '.notebook-card',
        '.notebook-item',
        '[class*="NotebookCard"]',
        '[class*="notebook"]',
        'div[class*="notebook-list"] a',
        'div[class*="notebooks"] a',
    ]

    notebooks = []
    for selector in notebook_selectors:
        try:
            elements = browser._page.query_selector_all(selector)
            if elements:
                for elem in elements:
                    try:
                        href = elem.get_attribute('href')
                        if href and '/notebook/' in href:
                            notebook_id = href.split('/')[-1].split('?')[0]
                            title_elem = elem.query_selector('h2, h3, span, div')
                            if title_elem:
                                title = title_elem.inner_text().strip()
                            else:
                                title = elem.inner_text().strip()

                            notebooks.append({
                                'id': notebook_id,
                                'title': title,
                                'url': f"https://notebooklm.google.com{href}"
                            })
                    except Exception:
                        continue

                if notebooks:
                    print(f"找到 {len(notebooks)} 个笔记本")
                    return notebooks
        except Exception:
            continue

    return notebooks


def save_to_library(notebooks, library):
    """保存笔记本到本地库

    Args:
        notebooks: 笔记本列表
        library: EnhancedNotebookLibrary 实例
    """
    print("保存到本地库...")
    for nb in notebooks:
        library.add_notebook(
            id=nb['id'],
            url=nb['url'],
            name=nb['title'],
            title=nb['title'],
        )


def main():
    parser = argparse.ArgumentParser(description="列出 NotebookLM 笔记本清单")
    parser.add_argument("-o", "--output", type=Path, default=Path("notebooks_list.md"), help="输出 Markdown 文件路径")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口")

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

        # 访问 NotebookLM 首页
        print("访问 NotebookLM...")
        browser._page.goto("https://notebooklm.google.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # 获取笔记本列表 - API 优先，DOM 回退
        notebooks = fetch_notebooks_from_api(browser)

        if not notebooks:
            notebooks = fetch_notebooks_from_dom(browser)

        if not notebooks:
            print("未找到笔记本，从本地库获取...")
            library = EnhancedNotebookLibrary()
            local_notebooks = library.list_notebooks()
            for nb in local_notebooks:
                notebooks.append({
                    'id': nb.id,
                    'title': nb.name or nb.title,
                    'url': nb.url,
                    'source_count': getattr(nb, 'source_count', 0),
                    'last_used': getattr(nb, 'last_used', 'N/A'),
                })

        # 保存到本地库
        if notebooks:
            library = EnhancedNotebookLibrary()
            save_to_library(notebooks, library)

        # 显示笔记本列表
        print()
        print("-" * 60)
        print("笔记本列表:")
        print("-" * 60)
        for i, nb in enumerate(notebooks, 1):
            print(f"{i}. {nb['title']}")
            print(f"   ID: {nb['id']}")
            print(f"   URL: {nb['url']}")
            print()

        # 保存为 Markdown
        output_lines = [
            "# NotebookLM 笔记本清单",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "| 笔记本 ID | 名称 | URL |",
            "|:--------|:-----|:---|",
        ]

        for nb in notebooks:
            output_lines.append(
                f"| `{nb['id']}` | {nb['title']} | {nb['url']} |"
            )

        output_lines.append("")
        output_lines.append(f"**共 {len(notebooks)} 个笔记本**")

        # 写入文件
        args.output.write_text("\n".join(output_lines), encoding='utf-8')
        print()
        print(f"✓ 已保存到: {args.output}")

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
