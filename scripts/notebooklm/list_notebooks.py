#!/usr/bin/env python3
"""列出 NotebookLM 笔记本。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from notebooklm.api_client import NotebookLMAPIClient
from notebooklm.library import EnhancedNotebookLibrary


def main() -> int:
    parser = argparse.ArgumentParser(description="列出 NotebookLM 笔记本")
    parser.add_argument("--storage-state", type=str, default="", help="storage_state.json 路径")
    args = parser.parse_args()

    client = NotebookLMAPIClient(storage_state=args.storage_state or None)
    try:
        notebooks = client.list_notebooks()
    finally:
        client.close()

    library = EnhancedNotebookLibrary()
    if notebooks:
        rows = []
        for nb in notebooks:
            rows.append({"id": nb.id, "title": nb.title, "url": nb.url})
            library.add_notebook(id=nb.id, url=nb.url, name=nb.title, title=nb.title)
    else:
        rows = [
            {"id": nb.id, "title": nb.name or nb.title, "url": nb.url}
            for nb in library.list_notebooks()
        ]

    if not rows:
        print("暂无笔记本")
        return 0

    print("=" * 60)
    print("NotebookLM 笔记本")
    print("=" * 60)
    for idx, row in enumerate(rows, 1):
        print(f"{idx}. {row['title']}")
        print(f"   ID: {row['id']}")
        print(f"   URL: {row['url']}")
    print()
    print(f"共 {len(rows)} 个笔记本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
