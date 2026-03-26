"""NotebookLM API 客户端适配层

封装 notebooklm-py 的 API 调用，提供同步接口。
"""
import asyncio
import importlib
import logging
import sys
from typing import List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass

# 使用 importlib 导入 notebooklm-py 库，避免与本地模块名冲突
_nbclient_module = None


def _get_notebook_client():
    """获取 notebooklm-py 的 NotebookLMClient 类

    由于本地模块名也是 notebooklm，需要临时移除 src 路径来导入 notebooklm-py 库。
    """
    global _nbclient_module
    if _nbclient_module is None:
        # 获取当前模块的路径
        current_dir = str(Path(__file__).parent)
        src_dir = str(Path(__file__).parent.parent)

        # 临时移除本地模块路径
        removed_paths = []
        for p in list(sys.path):
            if p in (current_dir, src_dir, 'src'):
                sys.path.remove(p)
                removed_paths.append(p)

        # 临时移除本地模块缓存
        cached_modules = {}
        for key in list(sys.modules.keys()):
            if key.startswith('notebooklm'):
                cached_modules[key] = sys.modules.pop(key)

        try:
            # 导入 notebooklm-py 库
            _nbclient_module = importlib.import_module('notebooklm')
        finally:
            # 恢复模块缓存
            for key, value in cached_modules.items():
                sys.modules[key] = value
            # 恢复路径
            for p in removed_paths:
                sys.path.insert(0, p)

    return _nbclient_module.NotebookLMClient


logger = logging.getLogger(__name__)


@dataclass
class NotebookAPIData:
    """API 返回的笔记本数据"""
    id: str
    title: str
    url: str

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
        }


class NotebookLMAPIClient:
    """NotebookLM API 客户端

    封装 notebooklm-py，提供同步接口。

    主要方法：
    - from_playwright_context(context): 从 Playwright 上下文创建
    - list_notebooks(): 列出笔记本
    - close(): 关闭客户端
    """

    def __init__(self, storage_state: Optional[Union[str, Path]] = None):
        """初始化客户端

        Args:
            storage_state: storage_state.json 路径
        """
        self.storage_state = str(storage_state) if storage_state else None
        self._client: Any = None  # NotebookLMClient 实例
        self._context = None  # 向后兼容

    @classmethod
    def from_playwright_context(cls, context) -> 'NotebookLMAPIClient':
        """从 Playwright 上下文创建客户端

        Args:
            context: Playwright BrowserContext

        Returns:
            NotebookLMAPIClient 实例
        """
        storage_state: Optional[str] = None

        # 兼容路径字符串/Path
        if isinstance(context, (str, Path)):
            storage_state = str(context)
        else:
            for attr in ("storage_state", "storage_state_path", "state_path"):
                value = getattr(context, attr, None)
                if value:
                    storage_state = str(value)
                    break

        instance = cls(storage_state=storage_state)
        instance._context = context
        return instance

    def _ensure_client(self):
        """确保客户端初始化"""
        if self._client is None:
            storage_path = self.storage_state or str(
                Path.home() / ".dedao-notebooklm" / "storage_state.json"
            )
            try:
                NotebookLMClient = _get_notebook_client()
                self._client = asyncio.run(
                    NotebookLMClient.from_storage(storage_path)
                )
            except Exception as e:
                logger.error(f"Failed to initialize client: {e}")

    def list_notebooks(self) -> List[NotebookAPIData]:
        """列出所有笔记本

        Returns:
            笔记本列表
        """
        self._ensure_client()

        if not self._client:
            logger.error("Client not initialized")
            return []

        try:
            notebooks = asyncio.run(self._client.notebooks.list())
            return [
                NotebookAPIData(
                    id=nb.id,
                    title=nb.title,
                    url=f"https://notebooklm.google.com/notebook/{nb.id}",
                )
                for nb in notebooks
            ]
        except Exception as e:
            logger.error(f"Failed to list notebooks: {e}")
            return []

    def close(self):
        """关闭客户端"""
        if self._client:
            try:
                asyncio.run(self._client.close())
            except Exception as e:
                logger.warning(f"Error closing client: {e}")
            finally:
                self._client = None

    def create_notebook(self, title: str) -> Optional[NotebookAPIData]:
        """创建笔记本。"""
        self._ensure_client()
        if not self._client:
            return None
        try:
            notebook = asyncio.run(self._client.notebooks.create(title=title))
            return NotebookAPIData(
                id=notebook.id,
                title=notebook.title,
                url=f"https://notebooklm.google.com/notebook/{notebook.id}",
            )
        except Exception as e:
            logger.error(f"Failed to create notebook: {e}")
            return None

    def upload_file(self, notebook_id: str, file_path: Union[str, Path]) -> bool:
        """上传文件到指定笔记本。"""
        self._ensure_client()
        if not self._client:
            return False
        try:
            asyncio.run(
                self._client.sources.add_file(
                    notebook_id=notebook_id,
                    file_path=str(file_path),
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False
