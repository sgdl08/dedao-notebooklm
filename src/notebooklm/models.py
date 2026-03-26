"""数据模型定义

与 notebooklm-py 的模型进行适配，提供现有代码期望的接口。
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class EnhancedNotebookInfo:
    """增强版笔记本信息

    现有代码期望的属性：
    - id, url, name, title, description
    - topics, tags, source_count, use_count, last_used
    """
    id: str
    url: str
    name: str = ""
    title: str = ""
    description: str = ""
    topics: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source_count: int = 0
    use_count: int = 0
    last_used: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'url': self.url,
            'name': self.name,
            'title': self.title,
            'description': self.description,
            'topics': self.topics,
            'tags': self.tags,
            'source_count': self.source_count,
            'use_count': self.use_count,
            'last_used': self.last_used,
        }


@dataclass
class NotebookLibraryStats:
    """笔记本库统计信息"""
    total_notebooks: int = 0
    total_sources: int = 0
    total_uses: int = 0
    most_used: Optional[str] = None
    recently_used: List[str] = field(default_factory=list)


@dataclass
class NotebookInfo:
    """简化版笔记本信息（用于 NotebookLibrary）"""
    id: str
    title: str
    url: str