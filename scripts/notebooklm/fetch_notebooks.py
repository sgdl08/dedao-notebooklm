#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""获取 NotebookLM 笔记本并保存到本地库。"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from notebooklm.api_client import NotebookLMAPIClient
from notebooklm.library import EnhancedNotebookLibrary


def main() -> int:
    parser = argparse.ArgumentParser(description="获取 NotebookLM 笔记本清单")
    parser.add_argument("-o", "--output", type=Path, default=Path("notebooks_list.md"), help="输出 Markdown 路径")
    parser.add_argument("--storage-state", type=str, default="", help="storage_state.json 路径")
    args = parser.parse_args()

    client = NotebookLMAPIClient(storage_state=args.storage_state or None)
    notebooks = []
    try:
        notebooks = [nb.to_dict() for nb in client.list_notebooks()]
    finally:
        client.close()

    library = EnhancedNotebookLibrary()
    if notebooks:
        for nb in notebooks:
            library.add_notebook(
                id=nb["id"],
                url=nb["url"],
                name=nb["title"],
                title=nb["title"],
            )
    else:
        # 回退本地库
        notebooks = [
            {"id": nb.id, "title": nb.name or nb.title, "url": nb.url}
            for nb in library.list_notebooks()
        ]

    output_lines = [
        "# NotebookLM 笔记本清单",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 笔记本 ID | 名称 | URL |",
        "|:--------|:-----|:---|",
    ]

    for nb in notebooks:
        output_lines.append(f"| `{nb['id']}` | {nb['title']} | {nb['url']} |")

    output_lines.append("")
    output_lines.append(f"**共 {len(notebooks)} 个笔记本**")

    args.output.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"✓ 已保存: {args.output}")
    print(f"共 {len(notebooks)} 个笔记本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
