"""加密/解密工具模块

用于电子书内容的 AES-CBC 解密。
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 默认 AES 密钥和 IV（从 dedao-dl 项目获取）
DEFAULT_AES_KEY = "3e4r06tjkpjcevlbslr3d96gdb5ahbmo"
DEFAULT_AES_IV = "6fd89a1b3a7f48fb"


def pkcs7_unpad(data: bytes) -> bytes:
    """PKCS7 去填充

    Args:
        data: 填充后的数据

    Returns:
        去填充后的数据
    """
    if not data:
        return data

    length = len(data)
    unpadding = data[length - 1]

    # 验证填充值的有效性
    if unpadding > length or unpadding == 0:
        logger.warning(f"无效的 PKCS7 填充值: {unpadding}")
        return data

    # 验证所有填充字节
    for i in range(1, unpadding + 1):
        if data[length - i] != unpadding:
            logger.warning("PKCS7 填充验证失败")
            return data

    return data[:length - unpadding]


def _normalize_aes_key(key: str) -> bytes:
    """归一化 AES 密钥长度。

    得到电子书当前使用 32 字节密钥（AES-256），但项目里也保留了旧逻辑。
    这里兼容 16/24/32 字节，并在非标准长度时向最近的合法长度补齐。
    """
    key_bytes = key.encode("utf-8")

    if len(key_bytes) in (16, 24, 32):
        return key_bytes

    if len(key_bytes) < 16:
        return key_bytes.ljust(16, b"\0")
    if len(key_bytes) < 24:
        return key_bytes.ljust(24, b"\0")
    if len(key_bytes) < 32:
        return key_bytes.ljust(32, b"\0")
    return key_bytes[:32]


def decrypt_aes_cbc(
    ciphertext_b64: str,
    key: Optional[str] = None,
    iv: Optional[str] = None
) -> str:
    """AES-CBC 解密

    解密得到电子书的 SVG 内容。

    Args:
        ciphertext_b64: Base64 编码的密文
        key: AES 密钥（可选，默认使用内置密钥）
        iv: 初始向量（可选，默认使用内置 IV）

    Returns:
        解密后的明文字符串
    """
    if not ciphertext_b64:
        return ""

    key = key or DEFAULT_AES_KEY
    iv = iv or DEFAULT_AES_IV

    try:
        # Base64 解码
        ciphertext = base64.b64decode(ciphertext_b64)
    except Exception as e:
        logger.error(f"Base64 解码错误: {e}")
        return ""

    try:
        from Crypto.Cipher import AES
    except ImportError:
        logger.error(
            "未安装 pycryptodome，请运行: pip install pycryptodome"
        )
        return ""

    try:
        # 得到电子书目前使用 32 字节密钥；非标准长度时做兜底处理。
        key_bytes = _normalize_aes_key(key)
        iv_bytes = iv.encode("utf-8")[:16].ljust(16, b"\0")

        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)

        # 解密
        plaintext = cipher.decrypt(ciphertext)

        # 去除 PKCS7 填充
        plaintext = pkcs7_unpad(plaintext)

        return plaintext.decode('utf-8')

    except Exception as e:
        logger.error(f"AES 解密错误: {e}")
        return ""


def decrypt_ebook_content(
    encrypted_svg: str,
    key: Optional[str] = None,
    iv: Optional[str] = None
) -> str:
    """解密电子书 SVG 内容

    这是 decrypt_aes_cbc 的别名，提供更语义化的接口。

    Args:
        encrypted_svg: 加密的 SVG 内容（Base64 编码）
        key: AES 密钥（可选）
        iv: 初始向量（可选）

    Returns:
        解密后的 SVG 内容
    """
    return decrypt_aes_cbc(encrypted_svg, key, iv)


def is_encrypted_content(content: str) -> bool:
    """检查内容是否为加密内容

    Args:
        content: 待检查的内容

    Returns:
        是否为加密内容
    """
    if not content:
        return False

    # 简单检查：尝试 Base64 解码
    try:
        decoded = base64.b64decode(content)
        # 如果解码成功且长度是 16 的倍数，可能是 AES 加密内容
        return len(decoded) % 16 == 0
    except Exception:
        return False
