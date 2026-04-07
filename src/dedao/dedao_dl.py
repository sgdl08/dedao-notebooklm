"""dedao-dl 工具封装

封装 dedao-dl Go 工具，提供 Python 接口。

dedao-dl 是一个成熟的得到下载工具，支持：
- 电子书下载（HTML/EPUB 格式）
- 课程下载
- 有声书下载

GitHub: https://github.com/yann0917/dedao-dl
"""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from browser_cookie3 import chrome

logger = logging.getLogger(__name__)

# 默认路径
DEFAULT_DEDAO_DL_PATH = Path.home() / "go" / "bin" / "dedao-dl"
DEFAULT_CONFIG_PATH = Path.home() / ".dedao" / "config.json"


@dataclass
class DedaoDLResult:
    """dedao-dl 执行结果"""
    success: bool
    output: str
    error: str
    exit_code: int
    output_files: List[Path]


class DedaoDLTool:
    """dedao-dl 工具封装

    提供对 dedao-dl Go 工具的 Python 封装，包括：
    - 工具检查和安装
    - 配置同步
    - 下载命令封装
    """

    def __init__(
        self,
        tool_path: Optional[Path] = None,
        config_path: Optional[Path] = None
    ):
        """初始化

        Args:
            tool_path: dedao-dl 可执行文件路径
            config_path: dedao-dl 配置文件路径
        """
        self.tool_path = Path(tool_path) if tool_path else DEFAULT_DEDAO_DL_PATH
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    @property
    def is_installed(self) -> bool:
        """检查工具是否已安装"""
        return self.tool_path.exists() and self.tool_path.is_file()

    def check_installation(self) -> Dict[str, Any]:
        """检查安装状态

        Returns:
            包含安装信息的字典
        """
        result = {
            "installed": False,
            "path": str(self.tool_path),
            "version": None,
            "config_exists": False,
            "logged_in": False,
        }

        if not self.is_installed:
            return result

        result["installed"] = True

        # 检查配置文件
        if self.config_path.exists():
            result["config_exists"] = True
            try:
                config = json.loads(self.config_path.read_text())
                cookie = config.get("cookie", {})
                # 检查关键字段
                has_gat = bool(cookie.get("GAT"))
                has_token = bool(cookie.get("token"))
                result["logged_in"] = has_gat and has_token
            except Exception:
                pass

        # 尝试获取版本
        try:
            proc = subprocess.run(
                [str(self.tool_path), "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                result["version"] = proc.stdout.strip()
        except Exception:
            pass

        return result

    def install(self) -> bool:
        """安装 dedao-dl

        通过 go install 安装。

        Returns:
            是否安装成功
        """
        try:
            # 检查 go 是否安装
            go_path = shutil.which("go")
            if not go_path:
                logger.error("Go 未安装，请先安装 Go")
                return False

            # 执行 go install
            logger.info("正在安装 dedao-dl...")
            proc = subprocess.run(
                ["go", "install", "github.com/yann0917/dedao-dl@latest"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if proc.returncode == 0:
                logger.info("dedao-dl 安装成功")
                return True
            else:
                logger.error(f"安装失败: {proc.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("安装超时")
            return False
        except Exception as e:
            logger.error(f"安装异常: {e}")
            return False

    def sync_cookies_from_chrome(self) -> bool:
        """从 Chrome 同步 Cookie 到 dedao-dl 配置

        Returns:
            是否同步成功
        """
        try:
            # 从 Chrome 获取 cookies
            cookies = chrome(domain_name='dedao.cn')
            cookie_dict = {c.name: c.value for c in cookies}

            # 构建 dedao-dl 配置格式
            config = {"cookie": {
                "GAT": cookie_dict.get("GAT", ""),
                "ISID": cookie_dict.get("ISID", ""),
                "iget": cookie_dict.get("iget", ""),
                "token": cookie_dict.get("token", ""),
                "_guard_device_id": cookie_dict.get("_guard_device_id", ""),
                "_sid": cookie_dict.get("_sid", ""),
                "acw_tc": cookie_dict.get("acw_tc", ""),
                "aliyungf_tc": cookie_dict.get("aliyungf_tc", ""),
            }}

            # 保存配置
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(config, indent=2))

            logger.info(f"Cookie 已同步到 {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"同步 Cookie 失败: {e}")
            return False

    def _run_command(self, args: List[str], timeout: int = 300) -> DedaoDLResult:
        """执行 dedao-dl 命令

        Args:
            args: 命令参数
            timeout: 超时时间（秒）

        Returns:
            执行结果
        """
        if not self.is_installed:
            return DedaoDLResult(
                success=False,
                output="",
                error="dedao-dl 未安装",
                exit_code=-1,
                output_files=[]
            )

        cmd = [str(self.tool_path)] + args
        logger.debug(f"执行命令: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return DedaoDLResult(
                success=proc.returncode == 0,
                output=proc.stdout,
                error=proc.stderr,
                exit_code=proc.returncode,
                output_files=[]  # 需要根据命令解析输出文件
            )

        except subprocess.TimeoutExpired:
            return DedaoDLResult(
                success=False,
                output="",
                error=f"命令超时（{timeout}秒）",
                exit_code=-1,
                output_files=[]
            )
        except Exception as e:
            return DedaoDLResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                output_files=[]
            )

    def who(self) -> DedaoDLResult:
        """检查登录状态

        Returns:
            执行结果
        """
        return self._run_command(["who"])

    def login(self) -> DedaoDLResult:
        """登录（打开登录页面）

        注意：这个命令会等待用户扫码。

        Returns:
            执行结果
        """
        # 先同步 Chrome cookies
        self.sync_cookies_from_chrome()
        return self._run_command(["login"], timeout=180)

    def list_ebooks(self, page: int = 1) -> DedaoDLResult:
        """列出电子书

        Args:
            page: 页码

        Returns:
            执行结果
        """
        return self._run_command(["ebook", "--page", str(page)])

    def download_ebook(
        self,
        ebook_id: int,
        output_format: str = "html",
        output_dir: Optional[Path] = None
    ) -> DedaoDLResult:
        """下载电子书

        Args:
            ebook_id: 电子书 ID（数字）
            output_format: 输出格式 (html, epub)
            output_dir: 输出目录

        Returns:
            执行结果
        """
        args = ["download", "ebook", "-i", str(ebook_id)]

        if output_format:
            args.extend(["--format", output_format])

        if output_dir:
            args.extend(["-o", str(output_dir)])

        result = self._run_command(args, timeout=600)

        # 尝试解析输出文件
        if result.success and output_dir:
            # 查找输出目录中的新文件
            result.output_files = list(output_dir.glob("*.html")) + list(output_dir.glob("*.epub"))

        return result

    def download_course(
        self,
        course_id: str,
        output_dir: Optional[Path] = None
    ) -> DedaoDLResult:
        """下载课程

        Args:
            course_id: 课程 ID
            output_dir: 输出目录

        Returns:
            执行结果
        """
        args = ["download", "course", "-i", course_id]

        if output_dir:
            args.extend(["-o", str(output_dir)])

        return self._run_command(args, timeout=600)


# 便捷函数
_tool_instance: Optional[DedaoDLTool] = None


def get_dedao_dl_tool() -> DedaoDLTool:
    """获取 dedao-dl 工具实例"""
    global _tool_instance
    if _tool_instance is None:
        _tool_instance = DedaoDLTool()
    return _tool_instance


def check_dl_tool() -> Dict[str, Any]:
    """检查 dedao-dl 工具状态"""
    return get_dedao_dl_tool().check_installation()


def sync_cookies() -> bool:
    """同步 Chrome cookies 到 dedao-dl"""
    return get_dedao_dl_tool().sync_cookies_from_chrome()
