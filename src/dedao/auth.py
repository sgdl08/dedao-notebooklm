"""得到 (Dedao) 认证模块

支持两种认证方式：
1. Cookie 认证 - 直接提供 Cookie 字符串
2. Chrome Cookie - 从 Chrome 浏览器自动获取 Cookie

不再支持 Playwright 扫码登录，推荐使用 dedao-dl 工具进行扫码登录。
"""

import json
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class DedaoAuth:
    """得到认证管理器

    使用 Cookie 进行认证。
    """

    def __init__(self, cookie: Optional[str] = None, config_path: Optional[Path] = None):
        """初始化认证

        Args:
            cookie: 得到网站的登录 Cookie
            config_path: 配置文件路径，默认 ~/.dedao-notebooklm/config.json
        """
        self._cookie: Optional[str] = cookie
        self._config_path = config_path or self._default_config_path()
        self._headers: Dict[str, str] = {}

    def _default_config_path(self) -> Path:
        """获取默认配置路径"""
        return Path.home() / ".dedao-notebooklm" / "config.json"

    @property
    def cookie(self) -> Optional[str]:
        """获取 Cookie"""
        if self._cookie:
            return self._cookie

        # 尝试从配置文件读取
        if self._config_path.exists():
            try:
                config = json.loads(self._config_path.read_text())
                return config.get("dedao_cookie")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"读取配置文件失败：{e}")

        return None

    @cookie.setter
    def cookie(self, value: str):
        """设置 Cookie"""
        self._cookie = value
        self._update_headers()

    @property
    def headers(self) -> Dict[str, str]:
        """获取请求头"""
        if not self._headers and self.cookie:
            self._update_headers()
        return self._headers.copy()

    def _update_headers(self):
        """更新请求头"""
        cookie = self.cookie
        if cookie:
            # 从 cookie 中提取 token
            token = ""
            for part in cookie.split("; "):
                if part.startswith("token="):
                    token = part.split("=", 1)[1]
                    break

            self._headers = {
                "Cookie": cookie,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.dedao.cn/",
                "Origin": "https://www.dedao.cn",
                "X-Token": token,
            }

    def save_config(self, cookie: Optional[str] = None):
        """保存配置到文件

        Args:
            cookie: 要保存的 Cookie，如果不传则使用当前的
        """
        cookie_to_save = cookie or self._cookie
        if not cookie_to_save:
            raise ValueError("没有可保存的 Cookie")

        # 确保目录存在
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取现有配置
        config = {}
        if self._config_path.exists():
            try:
                config = json.loads(self._config_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass

        # 更新配置
        config["dedao_cookie"] = cookie_to_save
        self._config_path.write_text(json.dumps(config, indent=2))
        logger.info(f"配置已保存到 {self._config_path}")

    def clear_config(self):
        """清除保存的配置"""
        if self._config_path.exists():
            self._config_path.unlink()
            logger.info("配置已清除")

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return bool(self.cookie)

    def load_from_chrome(self) -> bool:
        """从 Chrome 浏览器加载 Cookie

        Returns:
            是否成功加载
        """
        try:
            import browser_cookie3

            cookies = browser_cookie3.chrome(domain_name='dedao.cn')
            cookie_parts = []

            for c in cookies:
                cookie_parts.append(f"{c.name}={c.value}")

            if cookie_parts:
                cookie_str = "; ".join(cookie_parts)
                self.cookie = cookie_str
                logger.info("已从 Chrome 加载 Cookie")
                return True

            return False

        except ImportError:
            logger.error("未安装 browser_cookie3，请运行: pip install browser-cookie3")
            return False
        except Exception as e:
            logger.error(f"从 Chrome 加载 Cookie 失败: {e}")
            return False


def get_cookie_from_chrome() -> Optional[str]:
    """从 Chrome 获取 dedao.cn 的 Cookie

    Returns:
        Cookie 字符串，失败返回 None
    """
    try:
        import browser_cookie3

        cookies = browser_cookie3.chrome(domain_name='dedao.cn')
        cookie_parts = []

        for c in cookies:
            cookie_parts.append(f"{c.name}={c.value}")

        return "; ".join(cookie_parts) if cookie_parts else None

    except ImportError:
        logger.error("未安装 browser_cookie3，请运行: pip install browser-cookie3")
        return None
    except Exception as e:
        logger.error(f"获取 Chrome Cookie 失败: {e}")
        return None
