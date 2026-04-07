"""FFmpeg 音频/视频工具模块

提供音频和视频文件的合并、转换功能。
"""

import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    """FFmpeg 错误"""
    pass


def is_ffmpeg_available() -> bool:
    """检查 FFmpeg 是否可用

    Returns:
        FFmpeg 是否已安装
    """
    return shutil.which("ffmpeg") is not None


def check_ffmpeg() -> None:
    """检查 FFmpeg，如果不可用则抛出异常

    Raises:
        FFmpegError: FFmpeg 未安装时
    """
    if not is_ffmpeg_available():
        raise FFmpegError(
            "FFmpeg 未安装。请先安装 FFmpeg：\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: 从 https://ffmpeg.org/download.html 下载"
        )


def merge_audio_files(
    input_files: List[Path],
    output_file: Path,
    codec: str = "copy",
) -> Path:
    """合并多个音频文件

    Args:
        input_files: 输入文件列表
        output_file: 输出文件路径
        codec: 音频编码器（默认 copy）

    Returns:
        输出文件路径

    Raises:
        FFmpegError: 合并失败时
    """
    check_ffmpeg()

    if not input_files:
        raise FFmpegError("没有输入文件")

    logger.info(f"合并 {len(input_files)} 个音频文件到 {output_file}")

    # 创建临时文件列表
    list_file = output_file.parent / "filelist.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for file_path in input_files:
                # 使用相对路径或绝对路径
                abs_path = file_path.resolve()
                f.write(f"file '{abs_path}'\n")

        # 使用 concat 协议合并
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖输出文件
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", codec,
            str(output_file),
        ]

        logger.debug(f"执行命令：{' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg 错误输出：{result.stderr}")
            raise FFmpegError(f"合并音频失败：{result.stderr}")

        logger.info(f"音频合并完成：{output_file}")
        return output_file

    finally:
        # 清理临时文件
        if list_file.exists():
            list_file.unlink()


def merge_audio_video(
    audio_file: Path,
    video_file: Path,
    output_file: Path,
    audio_codec: str = "copy",
    video_codec: str = "copy",
) -> Path:
    """合并音频和视频文件

    Args:
        audio_file: 音频文件路径
        video_file: 视频文件路径
        output_file: 输出文件路径
        audio_codec: 音频编码器
        video_codec: 视频编码器

    Returns:
        输出文件路径

    Raises:
        FFmpegError: 合并失败时
    """
    check_ffmpeg()

    logger.info(f"合并音频和视频：{audio_file} + {video_file} -> {output_file}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video_file),
        "-i", str(audio_file),
        "-c:v", video_codec,
        "-c:a", audio_codec,
        str(output_file),
    ]

    logger.debug(f"执行命令：{' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"FFmpeg 错误输出：{result.stderr}")
        raise FFmpegError(f"合并音视频失败：{result.stderr}")

    logger.info(f"音视频合并完成：{output_file}")
    return output_file


def merge_ts_to_mp4(
    ts_files: List[Path],
    output_file: Path,
) -> Path:
    """合并 TS 文件为 MP4

    Args:
        ts_files: TS 文件列表
        output_file: 输出 MP4 文件路径

    Returns:
        输出文件路径

    Raises:
        FFmpegError: 合并失败时
    """
    check_ffmpeg()

    if not ts_files:
        raise FFmpegError("没有输入文件")

    logger.info(f"合并 {len(ts_files)} 个 TS 文件到 {output_file}")

    # 创建临时文件列表
    list_file = output_file.parent / "ts_filelist.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for file_path in ts_files:
                abs_path = file_path.resolve()
                f.write(f"file '{abs_path}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            str(output_file),
        ]

        logger.debug(f"执行命令：{' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg 错误输出：{result.stderr}")
            raise FFmpegError(f"合并 TS 失败：{result.stderr}")

        logger.info(f"TS 合并完成：{output_file}")
        return output_file

    finally:
        if list_file.exists():
            list_file.unlink()


def convert_audio(
    input_file: Path,
    output_file: Path,
    codec: str = "libmp3lame",
    bitrate: str = "192k",
) -> Path:
    """转换音频格式

    Args:
        input_file: 输入文件
        output_file: 输出文件
        codec: 音频编码器
        bitrate: 比特率

    Returns:
        输出文件路径

    Raises:
        FFmpegError: 转换失败时
    """
    check_ffmpeg()

    logger.info(f"转换音频：{input_file} -> {output_file}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_file),
        "-c:a", codec,
        "-b:a", bitrate,
        str(output_file),
    ]

    logger.debug(f"执行命令：{' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"FFmpeg 错误输出：{result.stderr}")
        raise FFmpegError(f"转换音频失败：{result.stderr}")

    logger.info(f"音频转换完成：{output_file}")
    return output_file


def get_media_info(file_path: Path) -> dict:
    """获取媒体文件信息

    需要安装 ffprobe（通常随 FFmpeg 一起安装）。

    Args:
        file_path: 媒体文件路径

    Returns:
        媒体信息字典
    """
    if not shutil.which("ffprobe"):
        logger.warning("ffprobe 不可用")
        return {}

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            import json
            return json.loads(result.stdout)

    except Exception as e:
        logger.error(f"获取媒体信息失败：{e}")

    return {}


def get_duration(file_path: Path) -> Optional[float]:
    """获取媒体文件时长（秒）

    Args:
        file_path: 媒体文件路径

    Returns:
        时长（秒），如果无法获取则返回 None
    """
    info = get_media_info(file_path)

    try:
        duration = float(info.get("format", {}).get("duration", 0))
        return duration if duration > 0 else None
    except (ValueError, TypeError):
        return None


def download_m3u8(
    m3u8_url: str,
    output_file: Path,
    headers: Optional[dict] = None,
) -> Path:
    """下载 M3U8 流媒体

    Args:
        m3u8_url: M3U8 URL
        output_file: 输出文件路径
        headers: 请求头

    Returns:
        输出文件路径

    Raises:
        FFmpegError: 下载失败时
    """
    check_ffmpeg()

    logger.info(f"下载 M3U8：{m3u8_url} -> {output_file}")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", m3u8_url,
        "-c", "copy",
        str(output_file),
    ]

    # 添加请求头
    if headers:
        header_str = ";".join(f"{k}={v}" for k, v in headers.items())
        cmd.extend(["-headers", header_str])

    logger.debug(f"执行命令：{' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"FFmpeg 错误输出：{result.stderr}")
        raise FFmpegError(f"下载 M3U8 失败：{result.stderr}")

    logger.info(f"M3U8 下载完成：{output_file}")
    return output_file
