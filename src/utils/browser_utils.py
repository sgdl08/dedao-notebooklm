"""浏览器工具类

提供人性化的浏览器操作，如模拟人类打字延迟等。
参考 notebooklm-skill 的 browser_utils 实现。

迁移自: https://github.com/PleasePrompto/notebooklm-skill
"""

import json
import random
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from playwright.sync_api import Page, BrowserContext, Playwright

logger = logging.getLogger(__name__)

# 尝试导入配置，如果失败则使用默认值
try:
    from notebooklm.config import (
        BROWSER_ARGS,
        TYPING_WPM_MIN,
        TYPING_WPM_MAX,
        TYPING_DELAY_MIN_MS,
        TYPING_DELAY_MAX_MS,
        TYPING_LONG_PAUSE_PROBABILITY,
        TYPING_LONG_PAUSE_MIN_MS,
        TYPING_LONG_PAUSE_MAX_MS,
    )
except ImportError:
    # 默认配置
    BROWSER_ARGS = [
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--no-first-run',
        '--no-default-browser-check',
    ]
    TYPING_WPM_MIN = 320
    TYPING_WPM_MAX = 480
    TYPING_DELAY_MIN_MS = 25
    TYPING_DELAY_MAX_MS = 75
    TYPING_LONG_PAUSE_PROBABILITY = 0.05
    TYPING_LONG_PAUSE_MIN_MS = 150
    TYPING_LONG_PAUSE_MAX_MS = 400


class StealthUtils:
    """隐身工具类

    提供人性化的浏览器操作，避免被检测为自动化。
    特性：
    - 随机打字延迟（320-480 WPM）
    - 5% 概率长暂停（150-400ms）
    - 鼠标移动轨迹模拟
    """

    @staticmethod
    def random_delay(min_ms: int = 100, max_ms: int = 500):
        """随机延迟

        Args:
            min_ms: 最小延迟（毫秒）
            max_ms: 最大延迟（毫秒）
        """
        delay = random.uniform(min_ms, max_ms) / 1000
        time.sleep(delay)

    @staticmethod
    def human_type(
        page: Page,
        selector: str,
        text: str,
        delay_range: tuple = None,
        wpm_range: tuple = None
    ):
        """模拟人类打字（增强版）

        特性：
        - 320-480 WPM 打字速度
        - 25-75ms 随机字符延迟
        - 5% 概率长暂停（150-400ms）

        Args:
            page: Playwright Page 对象
            selector: 输入框选择器
            text: 要输入的文本
            delay_range: 按键延迟范围（毫秒），默认使用配置
            wpm_range: 打字速度范围（WPM），默认使用配置
        """
        element = page.query_selector(selector)
        if not element:
            logger.warning(f"未找到元素：{selector}")
            return

        # 使用配置的延迟范围
        if delay_range is None:
            delay_range = (TYPING_DELAY_MIN_MS, TYPING_DELAY_MAX_MS)

        # 聚焦输入框
        element.focus()
        StealthUtils.random_delay(100, 300)

        # 逐字输入（模拟人类打字）
        for char in text:
            page.keyboard.type(char)

            # 基础随机延迟
            StealthUtils.random_delay(*delay_range)

            # 5% 概率长暂停（模拟思考）
            if random.random() < TYPING_LONG_PAUSE_PROBABILITY:
                StealthUtils.random_delay(
                    TYPING_LONG_PAUSE_MIN_MS,
                    TYPING_LONG_PAUSE_MAX_MS
                )

        # 输入完成后短暂延迟
        StealthUtils.random_delay(100, 200)

    @staticmethod
    def human_click(page: Page, selector: str):
        """模拟人类点击

        Args:
            page: Playwright Page 对象
            selector: 点击元素选择器
        """
        element = page.query_selector(selector)
        if not element:
            logger.warning(f"未找到元素：{selector}")
            return

        # 随机延迟后点击
        StealthUtils.random_delay(100, 300)
        element.click()
        StealthUtils.random_delay(100, 200)

    @staticmethod
    def realistic_click(page: Page, selector: str, move_steps: int = 5):
        """模拟真实点击（带鼠标移动轨迹）

        从源项目迁移，特性：
        - 计算元素中心点
        - 分步移动鼠标到目标位置
        - 点击前后的随机延迟

        Args:
            page: Playwright Page 对象
            selector: 点击元素选择器
            move_steps: 鼠标移动步数
        """
        element = page.query_selector(selector)
        if not element:
            logger.warning(f"未找到元素：{selector}")
            return

        try:
            # 获取元素边界框
            box = element.bounding_box()
            if not box:
                logger.warning(f"无法获取元素边界框：{selector}")
                element.click()
                return

            # 计算元素中心点
            x = box['x'] + box['width'] / 2
            y = box['y'] + box['height'] / 2

            # 分步移动鼠标（模拟人类移动轨迹）
            page.mouse.move(x, y, steps=move_steps)

            # 移动后延迟
            StealthUtils.random_delay(100, 300)

            # 点击
            element.click()

            # 点击后延迟
            StealthUtils.random_delay(100, 300)

        except Exception as e:
            logger.warning(f"realistic_click 失败，回退到普通点击: {e}")
            element.click()

    @staticmethod
    def scroll_random(page: Page):
        """随机滚动

        Args:
            page: Playwright Page 对象
        """
        # 随机滚动距离
        scroll_amount = random.randint(100, 500)
        page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        StealthUtils.random_delay(100, 300)

    @staticmethod
    def add_human_traces(page: Page):
        """添加人类痕迹（绕过检测）

        Args:
            page: Playwright Page 对象
        """
        # 覆盖 navigator.webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # 覆盖 plugins
        page.add_init_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)

        # 覆盖 languages
        page.add_init_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });
        """)


class BrowserFactory:
    """浏览器工厂

    创建和管理浏览器实例。
    支持 Playwright 和 Patchright（可选）。
    """

    @staticmethod
    def launch_persistent_context(
        playwright,
        user_data_dir: str,
        headless: bool = True,
        use_patchright: Optional[bool] = None,
        state_file: Optional[Path] = None
    ) -> BrowserContext:
        """启动持久化浏览器上下文

        Args:
            playwright: Playwright 实例
            user_data_dir: 用户数据目录
            headless: 是否无头模式
            use_patchright: 是否使用 Patchright（None=自动检测）
            state_file: 状态文件路径（用于注入 cookies）

        Returns:
            BrowserContext
        """
        # 自动检测是否使用 Patchright
        if use_patchright is None:
            try:
                import patchright
                use_patchright = True
                logger.info("检测到 Patchright，使用增强模式")
            except ImportError:
                use_patchright = False
                logger.debug("使用标准 Playwright")

        if use_patchright:
            # Patchright 模式：使用真实 Chrome
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",  # 使用真实 Chrome
                headless=headless,
                args=BROWSER_ARGS,
                ignore_default_args=["--enable-automation"],
            )
        else:
            # 标准 Playwright 模式
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                args=BROWSER_ARGS,
                ignore_default_args=["--enable-automation"],
            )

        # 注入 cookies（workaround for Playwright bug #36139）
        if state_file and state_file.exists():
            BrowserFactory._inject_cookies(context, state_file)

        # 添加隐身脚本
        for page in context.pages:
            StealthUtils.add_human_traces(page)

        return context

    @staticmethod
    def _inject_cookies(context: BrowserContext, state_file: Path):
        """注入 cookies 从状态文件

        Workaround for Playwright bug #36139:
        持久化上下文可能无法正确加载 session cookies

        Args:
            context: BrowserContext
            state_file: 状态文件路径（JSON 格式）
        """
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            cookies = state.get('cookies', [])
            if cookies:
                context.add_cookies(cookies)
                logger.info(f"已注入 {len(cookies)} 个 cookies")

        except Exception as e:
            logger.warning(f"注入 cookies 失败: {e}")

    @staticmethod
    def create_page(context: BrowserContext, viewport: dict = None) -> Page:
        """创建新页面

        Args:
            context: BrowserContext
            viewport: 视口大小

        Returns:
            Page
        """
        page = context.new_page()

        if viewport:
            page.set_viewport_size(viewport)
        else:
            page.set_viewport_size({"width": 1280, "height": 800})

        # 添加隐身脚本
        StealthUtils.add_human_traces(page)

        return page
