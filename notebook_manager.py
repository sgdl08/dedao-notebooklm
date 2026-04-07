#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""笔记本管理 CLI 工具

用法:
  python3 notebook_manager.py list
  python3 notebook_manager.py search <query>
  python3 notebook_manager.py add --url URL --name NAME [--description DESC] [--topics TOPICS]
  python3 notebook_manager.py activate <id>
  python3 notebook_manager.py remove <id>
  python3 notebook_manager.py stats
  python3 notebook_manager.py refresh [--headful]

迁移自: https://github.com/PleasePrompto/notebooklm-skill/scripts/notebook_manager.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from notebooklm.library import EnhancedNotebookLibrary, EnhancedNotebookInfo
from notebooklm.browser import NotebookLMBrowser
from notebooklm.api_client import NotebookLMAPIClient


def _parse_notebooks_from_response(response_text):
    """从 batchexecute 响应中解析笔记本列表

    NotebookLM batchexecute 响应格式:
    )]}'
    [["wrb.fr","wXbhsf","[[[\"笔记本名称\",[[[\"notebook-id\"],...]]]]]"],...]
    """
    notebooks = []

    try:
        # 移除前缀 )]}'
        if response_text.startswith(")]}'"):
            response_text = response_text[5:].strip()

        # 提取笔记本 ID 和标题
        # 格式: [["notebook-id"],"title",...]
        id_pattern = r'\[\["([a-f0-9-]{36})"\],"([^"]+)"'
        matches = re.findall(id_pattern, response_text)

        for notebook_id, title in matches:
            if title and not title.startswith('Q'):  # 过滤掉看起来像查询的标题
                notebooks.append({
                    'id': notebook_id,
                    'title': title,
                    'url': f"https://notebooklm.google.com/notebook/{notebook_id}",
                })

        print(f"[PARSE] 找到笔记本: {title} ({notebook_id})")

    except Exception as e:
        print(f"[PARSE] 解析失败: {e}")

    return notebooks


def cmd_list(args):
    """列出所有笔记本"""
    library = EnhancedNotebookLibrary()
    notebooks = library.list_notebooks()

    if not notebooks:
        print("暂无笔记本")
        return

    print("=" * 60)
    print("笔记本列表")
    print("=" * 60)
    print()

    for i, nb in enumerate(notebooks, 1):
        print(f"{i}. {nb.name or nb.title}")
        print(f"   ID: {nb.id}")
        print(f"   URL: {nb.url}")
        if nb.description:
            print(f"   描述: {nb.description[:50]}...")
        if nb.topics:
            print(f"   主题: {', '.join(nb.topics)}")
        if nb.tags:
            print(f"   标签: {', '.join(nb.tags)}")
        print(f"   源文件数: {nb.source_count}")
        print(f"   使用次数: {nb.use_count}")
        if nb.last_used:
            print(f"   最后使用: {nb.last_used}")
        print()

    print(f"共 {len(notebooks)} 个笔记本")


def cmd_search(args):
    """搜索笔记本"""
    library = EnhancedNotebookLibrary()
    results = library.search_notebooks(args.query)

    if not results:
        print(f"未找到匹配 '{args.query}' 的笔记本")
        return

    print("=" * 60)
    print(f"搜索结果: '{args.query}'")
    print("=" * 60)
    print()

    for i, nb in enumerate(results, 1):
        print(f"{i}. {nb.name or nb.title}")
        print(f"   ID: {nb.id}")
        print()

    print(f"共 {len(results)} 个匹配")


def cmd_add(args):
    """添加笔记本"""
    library = EnhancedNotebookLibrary()

    # 解析 topics
    topics = []
    if args.topics:
        topics = [t.strip() for t in args.topics.split(',')]

    # 解析 tags
    tags = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(',')]

    # 从 URL 提取 ID
    notebook_id = args.url.split('/')[-1].split('?')[0]

    library.add_notebook(
        id=notebook_id,
        url=args.url,
        name=args.name,
        title=args.name,
        description=args.description or "",
        topics=topics,
        tags=tags,
    )

    print(f"✓ 已添加笔记本: {args.name}")
    print(f"  ID: {notebook_id}")
    print(f"  URL: {args.url}")


def cmd_activate(args):
    """激活笔记本"""
    library = EnhancedNotebookLibrary()

    if library.set_active_notebook(args.id):
        nb = library.get_notebook(args.id)
        if nb:
            print(f"✓ 已激活: {nb.name or nb.title}")
        else:
            print(f"✓ 已激活笔记本: {args.id}")
    else:
        print(f"✗ 激活失败: 笔记本不存在")


def cmd_remove(args):
    """删除笔记本"""
    library = EnhancedNotebookLibrary()

    nb = library.get_notebook(args.id)
    if not nb:
        print(f"✗ 笔记本不存在: {args.id}")
        return

    name = nb.name or nb.title

    if library.remove_notebook(args.id):
        print(f"✓ 已删除: {name}")
    else:
        print(f"✗ 删除失败")


def cmd_stats(args):
    """显示统计信息"""
    library = EnhancedNotebookLibrary()
    stats = library.get_stats()

    print("=" * 60)
    print("笔记本库统计")
    print("=" * 60)
    print()
    print(f"总笔记本数: {stats.total_notebooks}")
    print(f"总源文件数: {stats.total_sources}")
    print(f"总使用次数: {stats.total_uses}")
    if stats.most_used:
        print(f"最常用笔记本: {stats.most_used}")
    if stats.recently_used:
        print(f"最近使用: {', '.join(stats.recently_used[:5])}")


def cmd_refresh(args):
    """从 NotebookLM 刷新笔记本列表

    自动从 NotebookLM 网站获取所有笔记本并更新本地库。
    使用网络请求拦截方式获取。
    """
    print("=" * 60)
    print("从 NotebookLM 刷新笔记本列表")
    print("=" * 60)
    print()

    browser = None
    try:
        # 启动浏览器
        print("启动浏览器...")
        browser = NotebookLMBrowser(headless=not args.headful)
        browser._ensure_browser()

        # 用于存储从网络请求中捕获的笔记本
        captured_notebooks = []

        # 拦截网络响应
        def handle_response(response):
            url = response.url
            # NotebookLM 使用 batchexecute API，rpcid=wXbhsf 返回笔记本列表
            if 'batchexecute' in url and 'wXbhsf' in url:
                try:
                    body = response.text()
                    if body and len(body) > 100:
                        print(f"[NETWORK] 捕获到笔记本列表响应")
                        # 解析响应
                        captured_notebooks.extend(_parse_notebooks_from_response(body))
                except Exception as e:
                    print(f"[NETWORK] 解析响应失败: {e}")

        browser._page.on('response', handle_response)

        # 访问 NotebookLM 首页
        print("访问 NotebookLM...")
        browser._page.goto("https://notebooklm.google.com/")
        time.sleep(8)  # 等待所有网络请求完成

        notebooks = captured_notebooks

        if not notebooks:
            print("未能获取笔记本列表")
            return

        # 保存到本地库
        library = EnhancedNotebookLibrary()
        added_count = 0
        updated_count = 0

        for nb in notebooks:
            existing = library.get_notebook(nb['id'])
            if existing:
                # 更新现有笔记本
                library.add_notebook(
                    id=nb['id'],
                    url=nb['url'],
                    name=nb.get('title', existing.name),
                    title=nb.get('title', existing.title),
                    source_count=nb.get('source_count', existing.source_count),
                )
                updated_count += 1
            else:
                # 添加新笔记本
                library.add_notebook(
                    id=nb['id'],
                    url=nb['url'],
                    name=nb.get('title', '未命名'),
                    title=nb.get('title', '未命名'),
                    source_count=nb.get('source_count', 0),
                )
                added_count += 1

        print()
        print(f"✓ 已添加 {added_count} 个新笔记本")
        print(f"✓ 已更新 {updated_count} 个笔记本")
        print(f"✓ 总计 {len(notebooks)} 个笔记本")

    except Exception as e:
        print(f"刷新失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if browser:
            print()
            print("等待 2 秒后关闭浏览器...")
            time.sleep(2)
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="笔记本管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有笔记本")
    list_parser.set_defaults(func=cmd_list)

    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索笔记本")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.set_defaults(func=cmd_search)

    # add 命令
    add_parser = subparsers.add_parser("add", help="添加笔记本")
    add_parser.add_argument("--url", required=True, help="笔记本 URL")
    add_parser.add_argument("--name", required=True, help="笔记本名称")
    add_parser.add_argument("--description", help="描述")
    add_parser.add_argument("--topics", help="主题（逗号分隔）")
    add_parser.add_argument("--tags", help="标签（逗号分隔）")
    add_parser.set_defaults(func=cmd_add)

    # activate 命令
    activate_parser = subparsers.add_parser("activate", help="激活笔记本")
    activate_parser.add_argument("id", help="笔记本 ID")
    activate_parser.set_defaults(func=cmd_activate)

    # remove 命令
    remove_parser = subparsers.add_parser("remove", help="删除笔记本")
    remove_parser.add_argument("id", help="笔记本 ID")
    remove_parser.set_defaults(func=cmd_remove)

    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="显示统计信息")
    stats_parser.set_defaults(func=cmd_stats)

    # refresh 命令
    refresh_parser = subparsers.add_parser("refresh", help="从 NotebookLM 刷新笔记本列表")
    refresh_parser.add_argument("--headful", action="store_true", help="显示浏览器窗口")
    refresh_parser.set_defaults(func=cmd_refresh)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
