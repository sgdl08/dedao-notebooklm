"""NotebookLM 浏览器适配层

使用 notebooklm-py 提供浏览器自动化功能。
内部使用异步 API，对外提供同步接口。
"""
import asyncio
import importlib
import logging
import sys
from pathlib import Path
from typing import Optional, Any, List, Dict

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


from .models import NotebookInfo

logger = logging.getLogger(__name__)


class NotebookLMBrowser:
    """NotebookLM 浏览器适配层

    对外提供同步接口，内部使用 notebooklm-py 异步 API。

    主要方法：
    - _ensure_browser(): 确保客户端初始化
    - is_authenticated(): 检查认证状态
    - create_notebook(title): 创建笔记本
    - upload_file(file_path): 上传文件
    - close(): 关闭客户端
    """

    def __init__(
        self,
        headless: bool = True,
        storage_state: Optional[Path] = None,
    ):
        """初始化浏览器

        Args:
            headless: 是否无头模式（保留参数，向后兼容）
            storage_state: Playwright storage_state.json 路径
        """
        self.headless = headless
        self.storage_state = storage_state or self._default_storage_state()
        self._client: Any = None  # NotebookLMClient 实例
        self._page = None  # 向后兼容属性
        self._context = None  # 向后兼容属性
        self._current_notebook_id: Optional[str] = None

    @staticmethod
    def _default_storage_state() -> Path:
        """默认 storage_state 路径"""
        return Path.home() / ".dedao-notebooklm" / "storage_state.json"

    def _ensure_browser(self):
        """确保客户端初始化"""
        if self._client is None:
            # 创建事件循环并初始化客户端
            self._client = asyncio.run(self._init_client())
            # 设置向后兼容属性
            self._context = self._client  # 简化兼容层
            self._page = self._client

    async def _init_client(self):
        """异步初始化客户端"""
        if not self.storage_state.exists():
            raise FileNotFoundError(
                f"Storage state not found: {self.storage_state}\n"
                "Please run 'notebooklm login' first."
            )

        NotebookLMClient = _get_notebook_client()
        client = await NotebookLMClient.from_storage(str(self.storage_state))
        return client

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self.storage_state.exists()

    def create_notebook(
        self,
        title: str,
        debug: bool = False
    ) -> Optional[NotebookInfo]:
        """创建笔记本

        Args:
            title: 笔记本标题
            debug: 是否调试模式

        Returns:
            NotebookInfo 或 None
        """
        self._ensure_browser()

        try:
            notebook = asyncio.run(self._client.notebooks.create(title=title))

            if debug:
                logger.debug(f"Created notebook: {notebook}")

            self._current_notebook_id = notebook.id

            return NotebookInfo(
                id=notebook.id,
                title=notebook.title,
                url=f"https://notebooklm.google.com/notebook/{notebook.id}",
            )
        except Exception as e:
            logger.error(f"Failed to create notebook: {e}")
            return None

    def upload_file(self, file_path: Path) -> bool:
        """上传文件到当前笔记本

        Args:
            file_path: 文件路径

        Returns:
            是否成功
        """
        self._ensure_browser()

        if not self._current_notebook_id:
            logger.error("No active notebook. Please create/open a notebook first.")
            return False

        try:
            asyncio.run(
                self._client.sources.add_file(
                    notebook_id=self._current_notebook_id,
                    file_path=str(file_path)
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False

    def upload_files(self, file_paths: List[Path]) -> Dict[str, int]:
        """批量上传文件到当前笔记本。"""
        success = 0
        failed = 0
        for file_path in file_paths:
            if self.upload_file(file_path):
                success += 1
            else:
                failed += 1
        return {"success": success, "failed": failed, "total": len(file_paths)}

    def list_notebooks(self) -> List[NotebookInfo]:
        """列出账户下笔记本。"""
        self._ensure_browser()
        try:
            notebooks = asyncio.run(self._client.notebooks.list())
            return [
                NotebookInfo(
                    id=nb.id,
                    title=nb.title,
                    url=f"https://notebooklm.google.com/notebook/{nb.id}",
                )
                for nb in notebooks
            ]
        except Exception as e:
            logger.error(f"Failed to list notebooks: {e}")
            return []

    def set_active_notebook(self, notebook_id: str) -> bool:
        """设置当前操作的目标笔记本。"""
        if not notebook_id:
            return False
        self._current_notebook_id = notebook_id
        return True

    @property
    def current_notebook_id(self) -> Optional[str]:
        """当前激活的笔记本 ID。"""
        return self._current_notebook_id

    def close(self):
        """关闭客户端"""
        if self._client:
            try:
                asyncio.run(self._client.close())
            except Exception as e:
                logger.warning(f"Error closing client: {e}")
            finally:
                self._client = None
