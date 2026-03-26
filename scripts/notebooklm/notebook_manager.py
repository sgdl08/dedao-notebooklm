#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NotebookLM 本地库管理工具。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from notebooklm.api_client import NotebookLMAPIClient
from notebooklm.library import EnhancedNotebookLibrary


def cmd_list(_args):
    library = EnhancedNotebookLibrary()
    notebooks = library.list_notebooks()
    if not notebooks:
        print("暂无笔记本")
        return
    for idx, nb in enumerate(notebooks, 1):
        print(f"{idx}. {nb.name or nb.title}")
        print(f"   ID: {nb.id}")
        print(f"   URL: {nb.url}")
    print(f"\n共 {len(notebooks)} 个笔记本")


def cmd_search(args):
    library = EnhancedNotebookLibrary()
    results = library.search_notebooks(args.query)
    if not results:
        print(f"未找到匹配 '{args.query}' 的笔记本")
        return
    for idx, nb in enumerate(results, 1):
        print(f"{idx}. {nb.name or nb.title}")
        print(f"   ID: {nb.id}")
    print(f"\n共 {len(results)} 个匹配")


def cmd_add(args):
    library = EnhancedNotebookLibrary()
    notebook_id = args.url.split("/")[-1].split("?")[0]
    library.add_notebook(
        id=notebook_id,
        url=args.url,
        name=args.name,
        title=args.name,
        description=args.description or "",
        topics=[t.strip() for t in args.topics.split(",")] if args.topics else [],
        tags=[t.strip() for t in args.tags.split(",")] if args.tags else [],
    )
    print(f"✓ 已添加笔记本: {args.name} ({notebook_id})")


def cmd_activate(args):
    library = EnhancedNotebookLibrary()
    if library.set_active_notebook(args.id):
        print(f"✓ 已激活: {args.id}")
    else:
        print("✗ 激活失败: 笔记本不存在")


def cmd_remove(args):
    library = EnhancedNotebookLibrary()
    if library.remove_notebook(args.id):
        print(f"✓ 已删除: {args.id}")
    else:
        print("✗ 删除失败: 笔记本不存在")


def cmd_stats(_args):
    library = EnhancedNotebookLibrary()
    stats = library.get_stats()
    print(f"总笔记本数: {stats.total_notebooks}")
    print(f"总源文件数: {stats.total_sources}")
    print(f"总使用次数: {stats.total_uses}")
    if stats.most_used:
        print(f"最常用笔记本: {stats.most_used}")
    if stats.recently_used:
        print(f"最近使用: {', '.join(stats.recently_used)}")


def cmd_refresh(args):
    client = NotebookLMAPIClient(storage_state=args.storage_state or None)
    try:
        notebooks = client.list_notebooks()
    finally:
        client.close()

    if not notebooks:
        print("未获取到远端笔记本（请确认 storage_state 已配置）")
        return

    library = EnhancedNotebookLibrary()
    added = 0
    updated = 0
    for nb in notebooks:
        existing = library.get_notebook(nb.id)
        library.add_notebook(
            id=nb.id,
            url=nb.url,
            name=nb.title,
            title=nb.title,
        )
        if existing:
            updated += 1
        else:
            added += 1

    print(f"✓ 已添加 {added} 个新笔记本")
    print(f"✓ 已更新 {updated} 个笔记本")
    print(f"✓ 总计 {len(notebooks)} 个笔记本")


def main():
    parser = argparse.ArgumentParser(description="笔记本管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    list_parser = subparsers.add_parser("list", help="列出所有笔记本")
    list_parser.set_defaults(func=cmd_list)

    search_parser = subparsers.add_parser("search", help="搜索笔记本")
    search_parser.add_argument("query", help="搜索关键词")
    search_parser.set_defaults(func=cmd_search)

    add_parser = subparsers.add_parser("add", help="添加笔记本")
    add_parser.add_argument("--url", required=True, help="笔记本 URL")
    add_parser.add_argument("--name", required=True, help="笔记本名称")
    add_parser.add_argument("--description", help="描述")
    add_parser.add_argument("--topics", help="主题（逗号分隔）")
    add_parser.add_argument("--tags", help="标签（逗号分隔）")
    add_parser.set_defaults(func=cmd_add)

    activate_parser = subparsers.add_parser("activate", help="激活笔记本")
    activate_parser.add_argument("id", help="笔记本 ID")
    activate_parser.set_defaults(func=cmd_activate)

    remove_parser = subparsers.add_parser("remove", help="删除笔记本")
    remove_parser.add_argument("id", help="笔记本 ID")
    remove_parser.set_defaults(func=cmd_remove)

    stats_parser = subparsers.add_parser("stats", help="显示统计信息")
    stats_parser.set_defaults(func=cmd_stats)

    refresh_parser = subparsers.add_parser("refresh", help="从 NotebookLM 刷新笔记本列表")
    refresh_parser.add_argument("--storage-state", type=str, default="", help="storage_state.json 路径")
    refresh_parser.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
