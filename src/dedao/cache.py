"""缓存管理模块

使用 SQLite 实现键值缓存存储，支持 TTL 和前缀查询。
"""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional, Any, List, Dict
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)


class Cache:
    """SQLite 缓存管理器

    提供类似 BadgerDB 的缓存功能：
    - TTL 支持
    - 前缀查询
    - JSON 序列化
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """初始化缓存

        Args:
            cache_dir: 缓存目录，默认为 ~/.dedao-notebooklm/cache/
        """
        self.cache_dir = cache_dir or Path.home() / ".dedao-notebooklm" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.cache_dir / "cache.db"
        self._lock = Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON cache(expires_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_key_prefix ON cache(key)
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值（会被 JSON 序列化）
            ttl_seconds: 过期时间（秒），None 表示永不过期

        Returns:
            是否设置成功
        """
        try:
            json_value = json.dumps(value, ensure_ascii=False)
            created_at = time.time()
            expires_at = created_at + ttl_seconds if ttl_seconds else None

            with self._lock:
                with self._get_connection() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO cache (key, value, created_at, expires_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (key, json_value, created_at, expires_at)
                    )
                    conn.commit()

            logger.debug(f"缓存已设置: {key}")
            return True

        except Exception as e:
            logger.error(f"设置缓存失败: {key}, 错误: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存值，如果不存在或已过期则返回默认值
        """
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        SELECT value, expires_at FROM cache WHERE key = ?
                        """,
                        (key,)
                    )
                    row = cursor.fetchone()

                    if row is None:
                        return default

                    # 检查是否过期
                    if row["expires_at"] and row["expires_at"] < time.time():
                        # 删除过期缓存
                        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                        conn.commit()
                        return default

                    return json.loads(row["value"])

        except Exception as e:
            logger.error(f"获取缓存失败: {key}, 错误: {e}")
            return default

    def delete(self, key: str) -> bool:
        """删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        try:
            with self._lock:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                    conn.commit()

            logger.debug(f"缓存已删除: {key}")
            return True

        except Exception as e:
            logger.error(f"删除缓存失败: {key}, 错误: {e}")
            return False

    def delete_prefix(self, prefix: str) -> int:
        """删除指定前缀的所有缓存

        Args:
            prefix: 键前缀

        Returns:
            删除的数量
        """
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "DELETE FROM cache WHERE key LIKE ?",
                        (prefix + "%",)
                    )
                    deleted_count = cursor.rowcount
                    conn.commit()

            logger.debug(f"已删除前缀 {prefix} 的缓存: {deleted_count} 条")
            return deleted_count

        except Exception as e:
            logger.error(f"删除前缀缓存失败: {prefix}, 错误: {e}")
            return 0

    def get_keys_with_prefix(self, prefix: str) -> List[str]:
        """获取指定前缀的所有键

        Args:
            prefix: 键前缀

        Returns:
            匹配的键列表
        """
        try:
            current_time = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT key FROM cache
                    WHERE key LIKE ? AND (expires_at IS NULL OR expires_at > ?)
                    """,
                    (prefix + "%", current_time)
                )
                return [row["key"] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"获取前缀键失败: {prefix}, 错误: {e}")
            return []

    def get_all_with_prefix(self, prefix: str) -> Dict[str, Any]:
        """获取指定前缀的所有键值对

        Args:
            prefix: 键前缀

        Returns:
            匹配的键值对字典
        """
        try:
            current_time = time.time()
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT key, value FROM cache
                    WHERE key LIKE ? AND (expires_at IS NULL OR expires_at > ?)
                    """,
                    (prefix + "%", current_time)
                )
                return {
                    row["key"]: json.loads(row["value"])
                    for row in cursor.fetchall()
                }

        except Exception as e:
            logger.error(f"获取前缀数据失败: {prefix}, 错误: {e}")
            return {}

    def clear_expired(self) -> int:
        """清除所有过期缓存

        Returns:
            清除的数量
        """
        try:
            current_time = time.time()
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                        (current_time,)
                    )
                    deleted_count = cursor.rowcount
                    conn.commit()

            if deleted_count > 0:
                logger.info(f"已清除过期缓存: {deleted_count} 条")

            return deleted_count

        except Exception as e:
            logger.error(f"清除过期缓存失败: {e}")
            return 0

    def clear_all(self) -> bool:
        """清除所有缓存

        Returns:
            是否清除成功
        """
        try:
            with self._lock:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM cache")
                    conn.commit()

            logger.info("已清除所有缓存")
            return True

        except Exception as e:
            logger.error(f"清除所有缓存失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            统计信息字典
        """
        try:
            current_time = time.time()
            with self._get_connection() as conn:
                # 总数
                total_cursor = conn.execute("SELECT COUNT(*) as count FROM cache")
                total = total_cursor.fetchone()["count"]

                # 有效数
                valid_cursor = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM cache
                    WHERE expires_at IS NULL OR expires_at > ?
                    """,
                    (current_time,)
                )
                valid = valid_cursor.fetchone()["count"]

                # 过期数
                expired_cursor = conn.execute(
                    """
                    SELECT COUNT(*) as count FROM cache
                    WHERE expires_at IS NOT NULL AND expires_at <= ?
                    """,
                    (current_time,)
                )
                expired = expired_cursor.fetchone()["count"]

                # 数据库大小
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    "total_entries": total,
                    "valid_entries": valid,
                    "expired_entries": expired,
                    "db_size_bytes": db_size,
                    "db_path": str(self.db_path),
                }

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {}


# 全局缓存实例
_global_cache: Optional[Cache] = None


def get_cache(cache_dir: Optional[Path] = None) -> Cache:
    """获取全局缓存实例

    Args:
        cache_dir: 缓存目录

    Returns:
        Cache 实例
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = Cache(cache_dir)
    return _global_cache


def set_cache(cache: Cache):
    """设置全局缓存实例"""
    global _global_cache
    _global_cache = cache


# 便捷函数
def cache_get(key: str, default: Any = None) -> Any:
    """获取缓存值"""
    return get_cache().get(key, default)


def cache_set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
    """设置缓存值"""
    return get_cache().set(key, value, ttl_seconds)


def cache_delete(key: str) -> bool:
    """删除缓存"""
    return get_cache().delete(key)


# 预定义的缓存键前缀
class CachePrefix:
    """缓存键前缀常量"""
    COURSE = "course:"
    CHAPTER = "chapter:"
    EBOOK = "ebook:"
    EBOOK_PAGE = "ebook_page:"
    AUDIOBOOK = "audiobook:"
    CHANNEL = "channel:"
    TOPIC = "topic:"
    USER = "user:"


# 预定义的 TTL（秒）
class CacheTTL:
    """缓存 TTL 常量"""
    COURSE_DETAIL = 2 * 60 * 60  # 2 小时
    EBOOK_PAGE = 24 * 60 * 60    # 24 小时
    USER_INFO = 60 * 60          # 1 小时
    CHAPTER_LIST = 2 * 60 * 60   # 2 小时
