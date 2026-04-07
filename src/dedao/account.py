"""多账户管理模块

支持多个得到账户的管理、切换和持久化存储。
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class Account:
    """账户模型"""
    uid: str  # 用户 ID
    name: str  # 用户名
    avatar: str = ""  # 头像 URL
    cookie: str = ""  # Cookie 字符串
    token: str = ""  # Token
    created_at: str = ""  # 创建时间
    last_used: str = ""  # 最后使用时间

    # 额外信息
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_used:
            self.last_used = self.created_at

    def touch(self):
        """更新最后使用时间"""
        self.last_used = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        """从字典创建"""
        return cls(**data)


class AccountManager:
    """账户管理器

    功能：
    - 添加/删除账户
    - 切换当前活动账户
    - 账户列表查看
    - 持久化存储
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """初始化账户管理器

        Args:
            config_dir: 配置目录，默认为 ~/.dedao-notebooklm/
        """
        self.config_dir = config_dir or Path.home() / ".dedao-notebooklm"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.accounts_file = self.config_dir / "accounts.json"
        self.accounts: Dict[str, Account] = {}  # uid -> Account
        self.active_uid: Optional[str] = None

        self._load()

    def _load(self):
        """从文件加载账户"""
        if not self.accounts_file.exists():
            logger.debug("账户文件不存在，使用空账户列表")
            return

        try:
            data = json.loads(self.accounts_file.read_text(encoding='utf-8'))
            accounts_data = data.get("accounts", {})
            self.active_uid = data.get("active_uid")

            for uid, account_data in accounts_data.items():
                self.accounts[uid] = Account.from_dict(account_data)

            logger.info(f"已加载 {len(self.accounts)} 个账户")

        except Exception as e:
            logger.error(f"加载账户文件失败: {e}")

    def _save(self):
        """保存账户到文件"""
        try:
            data = {
                "accounts": {
                    uid: account.to_dict()
                    for uid, account in self.accounts.items()
                },
                "active_uid": self.active_uid,
                "updated_at": datetime.now().isoformat(),
            }

            self.accounts_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logger.debug("账户已保存")

        except Exception as e:
            logger.error(f"保存账户文件失败: {e}")

    def add_account(
        self,
        uid: str,
        name: str,
        cookie: str,
        token: str = "",
        avatar: str = "",
        **kwargs
    ) -> Account:
        """添加或更新账户

        Args:
            uid: 用户 ID
            name: 用户名
            cookie: Cookie 字符串
            token: Token
            avatar: 头像 URL
            **kwargs: 其他账户信息

        Returns:
            Account 实例
        """
        now = datetime.now().isoformat()

        # 如果账户已存在，保留原有的创建时间
        existing = self.accounts.get(uid)
        created_at = existing.created_at if existing else now

        account = Account(
            uid=uid,
            name=name,
            cookie=cookie,
            token=token,
            avatar=avatar,
            created_at=created_at,
            last_used=now,
            extra=kwargs,
        )

        self.accounts[uid] = account

        # 如果是第一个账户，自动设为活动账户
        if len(self.accounts) == 1:
            self.active_uid = uid

        self._save()
        logger.info(f"账户已添加/更新: {name} ({uid})")

        return account

    def remove_account(self, uid: str) -> bool:
        """删除账户

        Args:
            uid: 用户 ID

        Returns:
            是否删除成功
        """
        if uid not in self.accounts:
            logger.warning(f"账户不存在: {uid}")
            return False

        del self.accounts[uid]

        # 如果删除的是活动账户，切换到第一个可用账户
        if self.active_uid == uid:
            self.active_uid = next(iter(self.accounts.keys())) if self.accounts else None

        self._save()
        logger.info(f"账户已删除: {uid}")

        return True

    def switch_account(self, uid: str) -> bool:
        """切换活动账户

        Args:
            uid: 用户 ID

        Returns:
            是否切换成功
        """
        if uid not in self.accounts:
            logger.warning(f"账户不存在: {uid}")
            return False

        self.active_uid = uid
        self.accounts[uid].touch()
        self._save()
        logger.info(f"已切换到账户: {self.accounts[uid].name} ({uid})")

        return True

    def get_active_account(self) -> Optional[Account]:
        """获取当前活动账户

        Returns:
            活动账户，如果没有则返回 None
        """
        if self.active_uid and self.active_uid in self.accounts:
            return self.accounts[self.active_uid]
        return None

    def get_account(self, uid: str) -> Optional[Account]:
        """获取指定账户

        Args:
            uid: 用户 ID

        Returns:
            账户实例
        """
        return self.accounts.get(uid)

    def list_accounts(self) -> List[Account]:
        """获取所有账户列表

        Returns:
            账户列表
        """
        return list(self.accounts.values())

    def get_active_cookie(self) -> str:
        """获取当前活动账户的 Cookie

        Returns:
            Cookie 字符串
        """
        account = self.get_active_account()
        return account.cookie if account else ""

    def get_active_token(self) -> str:
        """获取当前活动账户的 Token

        Returns:
            Token 字符串
        """
        account = self.get_active_account()
        return account.token if account else ""

    def has_accounts(self) -> bool:
        """检查是否有账户

        Returns:
            是否有账户
        """
        return len(self.accounts) > 0

    def count(self) -> int:
        """获取账户数量

        Returns:
            账户数量
        """
        return len(self.accounts)

    def clear_all(self):
        """清除所有账户"""
        self.accounts.clear()
        self.active_uid = None
        self._save()
        logger.info("所有账户已清除")


# 全局账户管理器实例
_global_account_manager: Optional[AccountManager] = None


def get_account_manager(config_dir: Optional[Path] = None) -> AccountManager:
    """获取全局账户管理器实例

    Args:
        config_dir: 配置目录

    Returns:
        AccountManager 实例
    """
    global _global_account_manager
    if _global_account_manager is None:
        _global_account_manager = AccountManager(config_dir)
    return _global_account_manager


def set_account_manager(manager: AccountManager):
    """设置全局账户管理器实例"""
    global _global_account_manager
    _global_account_manager = manager


# 便捷函数
def get_current_account() -> Optional[Account]:
    """获取当前活动账户"""
    return get_account_manager().get_active_account()


def get_current_cookie() -> str:
    """获取当前活动账户的 Cookie

    优先从 AccountManager 获取，如果没有则从 config.json 获取。
    """
    # 首先尝试从账户管理器获取
    manager = get_account_manager()
    cookie = manager.get_active_cookie()
    if cookie:
        return cookie

    # 回退到 config.json
    config_path = manager.config_dir / "config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding='utf-8'))
            return data.get("dedao_cookie", "")
        except Exception as e:
            logger.debug(f"读取 config.json 失败: {e}")

    return ""


def get_current_token() -> str:
    """获取当前活动账户的 Token"""
    return get_account_manager().get_active_token()
