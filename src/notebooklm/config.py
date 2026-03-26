"""配置常量

提供浏览器配置、打字延迟等参数。
"""
from pathlib import Path

# 默认存储路径
DEFAULT_DATA_DIR = Path.home() / ".dedao-notebooklm"
DEFAULT_STORAGE_STATE = DEFAULT_DATA_DIR / "storage_state.json"
DEFAULT_LIBRARY_PATH = DEFAULT_DATA_DIR / "library.json"

# 浏览器参数
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--no-first-run',
    '--no-default-browser-check',
]

# 打字模拟参数
TYPING_WPM_MIN = 320
TYPING_WPM_MAX = 480
TYPING_DELAY_MIN_MS = 25
TYPING_DELAY_MAX_MS = 75
TYPING_LONG_PAUSE_PROBABILITY = 0.05
TYPING_LONG_PAUSE_MIN_MS = 150
TYPING_LONG_PAUSE_MAX_MS = 400