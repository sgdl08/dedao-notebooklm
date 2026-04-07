"""基础客户端

提供通用的 HTTP 请求、认证、错误处理功能。
"""

import json
import logging
from typing import Optional, Dict, Any, Callable
from pathlib import Path

import requests

from .auth import DedaoAuth
from .constants import DEDIAO_API_BASE

logger = logging.getLogger(__name__)


class DedaoAPIError(Exception):
    """得到 API 错误"""

    def __init__(self, message: str, code: Optional[int] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code

    def __str__(self):
        parts = [super().__str__()]
        if self.code is not None:
            parts.append(f"(code={self.code})")
        if self.status_code is not None:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)


class DedaoNetworkError(DedaoAPIError):
    """网络错误"""
    pass


class DedaoAuthError(DedaoAPIError):
    """认证错误"""
    pass


class BaseClient:
    """基础客户端

    提供通用的 HTTP 请求功能，子类继承后实现特定业务的 API 方法。
    """

    def __init__(
        self,
        cookie: Optional[str] = None,
        base_url: str = DEDIAO_API_BASE,
        timeout: int = 30,
        debug: bool = False
    ):
        """初始化客户端

        Args:
            cookie: 得到网站的登录 Cookie
            base_url: API 基础 URL
            timeout: 请求超时时间（秒）
            debug: 是否开启调试模式
        """
        self._auth = DedaoAuth(cookie)
        self._base_url = base_url
        self._timeout = timeout
        self._debug = debug
        self._session = requests.Session()

        # 更新请求头
        if self._auth.headers:
            self._session.headers.update(self._auth.headers)

    @property
    def cookie(self) -> Optional[str]:
        """获取当前 Cookie"""
        return self._auth.cookie

    @cookie.setter
    def cookie(self, value: str):
        """设置 Cookie"""
        self._auth.cookie = value
        self._session.headers.update(self._auth.headers)

    def set_cookie(self, cookie: str):
        """设置 Cookie（别名）"""
        self.cookie = cookie

    def _request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送 HTTP 请求

        Args:
            method: HTTP 方法
            url: 请求 URL（相对路径或完整 URL）
            **kwargs: 传递给 requests 的其他参数

        Returns:
            API 响应数据

        Raises:
            DedaoNetworkError: 网络错误
            DedaoAuthError: 认证错误
            DedaoAPIError: API 错误
        """
        # 构建完整 URL
        if not url.startswith(("http://", "https://")):
            url = f"{self._base_url}{url}"

        try:
            response = self._session.request(
                method,
                url,
                timeout=self._timeout,
                **kwargs
            )
            response.raise_for_status()

            data = response.json()

            # 调试模式：打印原始返回
            if self._debug:
                logger.debug(f"API 响应 ({url}):")
                logger.debug(json.dumps(data, indent=2, ensure_ascii=False))

            # 解析响应
            return self._parse_response(data)

        except requests.exceptions.Timeout:
            raise DedaoNetworkError("请求超时，请检查网络连接")
        except requests.exceptions.ConnectionError:
            raise DedaoNetworkError("连接失败，请检查网络或得到网站是否可访问")
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 401:
                raise DedaoAuthError("认证失败，请重新登录", status_code=401)
            elif status_code == 403:
                raise DedaoAuthError("访问被拒绝，可能没有权限", status_code=403)
            raise DedaoAPIError(f"HTTP 错误", status_code=status_code)
        except json.JSONDecodeError as e:
            raise DedaoAPIError(f"解析响应失败：{e}")
        except DedaoAPIError:
            raise
        except Exception as e:
            raise DedaoAPIError(f"未知错误：{e}")

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析 API 响应

        得到 API 的响应格式：
        {
            "h": {"c": 0, "e": "", "s": 123, "t": 0},
            "c": {...实际数据...}
        }

        或者旧格式：
        {
            "code": 0,
            "data": {...}
        }

        Args:
            data: 原始响应数据

        Returns:
            实际数据部分

        Raises:
            DedaoAPIError: API 返回错误
        """
        # 新格式：h/c 结构
        if "h" in data:
            header = data.get("h", {})
            code = header.get("c")

            if code not in (0, None):
                error_msg = header.get("e") or "未知错误"
                raise DedaoAPIError(error_msg, code=code)

            return data

        # 旧格式：code/data 结构
        if "code" in data:
            code = data.get("code")
            if code not in (0, 200, None):
                error_msg = data.get("msg") or data.get("message") or "未知错误"
                raise DedaoAPIError(error_msg, code=code)

        return data

    def _get_data(self, response: Dict[str, Any]) -> Any:
        """从响应中提取数据

        兼容多种响应格式。

        Args:
            response: API 响应

        Returns:
            数据部分
        """
        # 新格式
        if "c" in response:
            return response.get("c")
        # 旧格式
        if "data" in response:
            return response.get("data")
        return response

    def _get_list(self, response: Dict[str, Any], key: str = "list") -> list:
        """从响应中提取列表

        Args:
            response: API 响应
            key: 列表字段名

        Returns:
            列表数据
        """
        data = self._get_data(response)
        if isinstance(data, dict):
            return data.get(key, [])
        if isinstance(data, list):
            return data
        return []

    def check_auth(self) -> Dict[str, Any]:
        """检查认证状态

        Returns:
            用户信息字典

        Raises:
            DedaoAuthError: 未认证或认证失效
        """
        try:
            # 尝试获取用户信息来验证认证状态
            data = self._request("GET", "/api/pc/user/info")
            user_info = self._get_data(data)

            if not user_info:
                raise DedaoAuthError("无法获取用户信息")

            return user_info

        except DedaoAPIError:
            raise DedaoAuthError("认证失效，请重新登录")

    def is_authenticated(self) -> bool:
        """检查是否已认证

        Returns:
            是否已认证
        """
        try:
            self.check_auth()
            return True
        except DedaoAuthError:
            return False

    def save_config(self, cookie: Optional[str] = None):
        """保存 Cookie 配置"""
        self._auth.save_config(cookie)

    def download_file(self, url: str, save_path: Path) -> Path:
        """下载文件

        Args:
            url: 文件 URL
            save_path: 保存路径

        Returns:
            保存的文件路径
        """
        logger.info(f"下载文件：{url} -> {save_path}")

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with self._session.get(url, stream=True) as response:
            response.raise_for_status()

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        logger.info(f"文件已下载到 {save_path}")
        return save_path
