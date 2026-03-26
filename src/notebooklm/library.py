"""笔记本本地库管理

提供本地 JSON 存储，管理笔记本元数据。
这是纯本地功能，不依赖 notebooklm-py。
"""
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import EnhancedNotebookInfo, NotebookLibraryStats


class EnhancedNotebookLibrary:
    """增强版笔记本库

    本地 JSON 存储，提供：
    - list_notebooks(): 列出所有笔记本
    - search_notebooks(query): 搜索笔记本
    - add_notebook(...): 添加笔记本
    - get_notebook(id): 获取笔记本
    - set_active_notebook(id): 设置激活笔记本
    - remove_notebook(id): 删除笔记本
    - get_stats(): 获取统计信息
    """

    DEFAULT_LIBRARY_PATH = Path.home() / ".dedao-notebooklm" / "library.json"

    def __init__(self, library_path: Optional[Path] = None):
        self.library_path = library_path or self.DEFAULT_LIBRARY_PATH
        self._library: dict = self._load_library()

    def _load_library(self) -> dict:
        """加载本地库"""
        if self.library_path.exists():
            try:
                return json.loads(self.library_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                return {"notebooks": {}, "active_id": None}
        return {"notebooks": {}, "active_id": None}

    def _save_library(self):
        """保存本地库"""
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        self.library_path.write_text(
            json.dumps(self._library, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def list_notebooks(self) -> List[EnhancedNotebookInfo]:
        """列出所有笔记本"""
        return [
            EnhancedNotebookInfo(**nb_data)
            for nb_data in self._library.get("notebooks", {}).values()
        ]

    def search_notebooks(self, query: str) -> List[EnhancedNotebookInfo]:
        """搜索笔记本"""
        query = query.lower()
        return [
            nb for nb in self.list_notebooks()
            if query in (nb.name or "").lower()
            or query in (nb.title or "").lower()
            or query in (nb.description or "").lower()
        ]

    def add_notebook(
        self,
        id: str,
        url: str,
        name: str = "",
        title: str = "",
        description: str = "",
        topics: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        source_count: int = 0,
    ):
        """添加或更新笔记本"""
        existing = self._library["notebooks"].get(id, {})

        self._library["notebooks"][id] = {
            "id": id,
            "url": url,
            "name": name or existing.get("name", ""),
            "title": title or existing.get("title", ""),
            "description": description or existing.get("description", ""),
            "topics": topics or existing.get("topics", []),
            "tags": tags or existing.get("tags", []),
            "source_count": source_count or existing.get("source_count", 0),
            "use_count": existing.get("use_count", 0),
            "last_used": existing.get("last_used"),
            "created_at": existing.get("created_at", datetime.now().isoformat()),
        }
        self._save_library()

    def get_notebook(self, notebook_id: str) -> Optional[EnhancedNotebookInfo]:
        """获取笔记本"""
        nb_data = self._library["notebooks"].get(notebook_id)
        if nb_data:
            return EnhancedNotebookInfo(**nb_data)
        return None

    def set_active_notebook(self, notebook_id: str) -> bool:
        """设置激活笔记本"""
        if notebook_id in self._library["notebooks"]:
            self._library["active_id"] = notebook_id
            self._save_library()
            return True
        return False

    def get_active_notebook_id(self) -> Optional[str]:
        """获取当前激活笔记本 ID。"""
        return self._library.get("active_id")

    def remove_notebook(self, notebook_id: str) -> bool:
        """删除笔记本"""
        if notebook_id in self._library["notebooks"]:
            del self._library["notebooks"][notebook_id]
            if self._library["active_id"] == notebook_id:
                self._library["active_id"] = None
            self._save_library()
            return True
        return False

    def get_stats(self) -> NotebookLibraryStats:
        """获取统计信息"""
        notebooks = self.list_notebooks()
        most_used = max(notebooks, key=lambda x: x.use_count).name if notebooks else None
        recently_used = sorted(
            [nb for nb in notebooks if nb.last_used],
            key=lambda x: x.last_used,
            reverse=True
        )[:5]

        return NotebookLibraryStats(
            total_notebooks=len(notebooks),
            total_sources=sum(nb.source_count for nb in notebooks),
            total_uses=sum(nb.use_count for nb in notebooks),
            most_used=most_used,
            recently_used=[nb.name or nb.title for nb in recently_used],
        )


class NotebookLibrary:
    """简化版笔记本库（向后兼容）"""

    def __init__(self):
        self._library = EnhancedNotebookLibrary()

    def add_notebook(self, notebook_id: str, title: str, url: str):
        """添加笔记本"""
        self._library.add_notebook(
            id=notebook_id,
            url=url,
            name=title,
            title=title,
        )
