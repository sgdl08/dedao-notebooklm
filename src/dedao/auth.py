"""得到 (Dedao) 认证模块"""

import json
import logging
import time
from typing import Optional, Dict, Callable
from pathlib import Path
import requests

logger = logging.getLogger(__name__)


class DedaoQRCodeLogin:
    """得到扫码登录

    使用 Playwright 打开登录页面，用户扫码登录后自动提取 Cookie。
    """

    def __init__(self, headless: bool = False):
        """初始化扫码登录

        Args:
            headless: 是否无头模式（扫码登录建议设为 False）
        """
        self.headless = headless
        self._page = None
        self._context = None
        self._playwright = None

    def login(self, timeout: int = 120) -> Optional[str]:
        """执行扫码登录

        Args:
            timeout: 超时时间（秒），默认 120 秒

        Returns:
            登录成功后返回 Cookie，失败返回 None
        """
        try:
            from playwright.sync_api import sync_playwright

            print("正在打开得到登录页面...")
            print("请使用得到 App 扫码登录")

            self._playwright = sync_playwright().start()

            # 启动浏览器
            browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ]
            )

            self._context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # 覆盖 navigator.webdriver
            self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            self._page = self._context.new_page()

            # 访问登录页面 - 得到使用扫码登录入口
            self._page.goto("https://www.dedao.cn/", wait_until="domcontentloaded")

            # 查找并点击登录按钮（如果有）
            try:
                login_button = self._page.query_selector('a[href*="login"], button:has-text("登录"), button:has-text("登陆")')
                if login_button:
                    login_button.click()
                    self._page.wait_for_url(lambda url: 'login' in url.lower() or url != 'https://www.dedao.cn/', timeout=5000)
            except Exception:
                pass  # 可能已经在登录页面或直接显示二维码

            print("等待扫码登录...")

            # 轮询检查登录状态（以 API 可用为准，避免误判）
            start_time = time.time()
            cookie = None

            while time.time() - start_time < timeout:
                # 先提取当前 cookie，并以接口探测验证登录态
                candidate_cookie = self._extract_cookie()
                if candidate_cookie and self._validate_cookie(candidate_cookie):
                    print("检测到登录成功！")
                    cookie = candidate_cookie
                    break

                time.sleep(2)

            # 关闭浏览器
            browser.close()
            self._playwright.stop()

            if cookie:
                print("扫码登录成功！")
                return cookie
            else:
                print(f"扫码登录超时（{timeout}秒）")
                return None

        except ImportError:
            print("错误：playwright 未安装")
            print("请运行：pip install playwright && playwright install")
            return None
        except Exception as e:
            print(f"登录过程出错：{e}")
            if self._playwright:
                self._playwright.stop()
            return None

    def _extract_cookie(self) -> str:
        """提取 Cookie 字符串"""
        cookies = self._context.cookies()
        cookie_parts = []

        for c in cookies:
            if c.get("domain", "").endswith("dedao.cn"):
                cookie_parts.append(f"{c['name']}={c['value']}")

        return "; ".join(cookie_parts)

    def _validate_cookie(self, cookie: str) -> bool:
        """验证 cookie 是否真正可用。"""
        if not cookie:
            return False
        headers = {
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.dedao.cn/",
            "Origin": "https://www.dedao.cn",
            "Content-Type": "application/json",
        }
        payload = {
            "category": "all",
            "display_group": True,
            "filter": "all",
            "group_id": 0,
            "order": "study",
            "filter_complete": 0,
            "page": 1,
            "page_size": 1,
            "sort_type": "desc",
        }
        try:
            resp = requests.post(
                "https://www.dedao.cn/api/hades/v2/product/list",
                json=payload,
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return False
            data = resp.json()
            # code=0 或返回 c/data 结构均视为有效
            if data.get("code") in (0, 200):
                return True
            if isinstance(data.get("c"), dict) or isinstance(data.get("data"), dict):
                return True
            return False
        except Exception:
            return False

    def close(self):
        """关闭浏览器资源"""
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass


class DedaoAuth:
    """得到认证管理器

    使用 Cookie 进行认证。用户需要从浏览器获取登录后的 Cookie。
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
        if self._cookie:
            self._headers = {
                "Cookie": self._cookie,
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.dedao.cn/",
                "Origin": "https://www.dedao.cn",
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

    def extract_cookie_from_browser(self) -> Optional[str]:
        """从浏览器提取 Cookie 的说明

        用户需要手动从浏览器获取 Cookie：
        1. 登录 https://www.dedao.cn
        2. 打开开发者工具 (F12)
        3. 切换到 Network 标签
        4. 刷新页面
        5. 找到任意 API 请求，复制 Cookie 值

        或者使用浏览器扩展导出 Cookie。
        """
        return None
