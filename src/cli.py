"""CLI entry point for dedao-notebooklm."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

import click

SRC_DIR = Path(__file__).resolve().parent
SRC_DIR_STR = str(SRC_DIR)
if sys.path[:1] != [SRC_DIR_STR]:
    try:
        sys.path.remove(SRC_DIR_STR)
    except ValueError:
        pass
    sys.path.insert(0, SRC_DIR_STR)

from ai_pack import ChapterSource, build_query_context, export_ai_pack
from course_ppts import (
    DEFAULT_EXCLUDE_KEYWORDS,
    DEFAULT_LANGUAGE,
    DEFAULT_PROMPT,
    run_course_ppts,
)
from course_sync import CourseSyncService
from data_migration import migrate_project_data
from dedao import DedaoAPIError, DedaoClient, DedaoQRCodeLogin
from dedao.downloader import CourseDownloader
from utils import get_config, load_config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _configure_stdio() -> None:
    """Use UTF-8 stdio when available so Windows consoles print safely."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _echo(ctx: click.Context, payload: Any, *, pretty: bool = True) -> None:
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None))
        return

    if isinstance(payload, str):
        click.echo(payload)
        return

    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _fail(ctx: click.Context, code: str, message: str, detail: Any = None, exit_code: int = 1) -> None:
    if ctx.obj.get("json"):
        payload = {"ok": False, "error": {"code": code, "message": message, "detail": detail}}
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        click.echo(f"错误: {message}", err=True)
        if detail:
            click.echo(f"detail: {detail}", err=True)
    raise SystemExit(exit_code)


def _resolve_cookie(ctx: click.Context) -> str:
    config = get_config()
    cookie = config.dedao_cookie
    if not cookie:
        _fail(ctx, "auth_required", "请先登录：dedao-nb login --cookie <cookie>")
    return cookie


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True, dir_okay=False), help="配置文件路径")
@click.option("--verbose", "-v", is_flag=True, help="显示详细日志")
@click.option("--debug", is_flag=True, help="调试模式，打印更多底层错误信息")
@click.option("--json", "json_output", is_flag=True, help="输出 JSON，方便脚本、Codex、OpenClaw 调用")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], verbose: bool, debug: bool, json_output: bool):
    """得到课程下载、同步、NotebookLM 上传与课程 PPT 生成工具。"""
    if config:
        load_config(Path(config))
    else:
        load_config()

    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["json"] = json_output

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option("--cookie", "-k", help="得到 Cookie")
@click.option("--qrcode", "-q", is_flag=True, help="使用二维码登录")
@click.pass_context
def login(ctx: click.Context, cookie: Optional[str], qrcode: bool):
    """登录得到账号。"""
    config = get_config()

    if not cookie and not qrcode:
        _fail(ctx, "invalid_args", "请使用 --cookie 或 --qrcode 登录")

    if qrcode:
        try:
            qr_login = DedaoQRCodeLogin()
            cookie = qr_login.login()
        except Exception as exc:
            _fail(ctx, "qrcode_login_failed", "二维码登录失败", str(exc))

    if not cookie:
        _fail(ctx, "login_failed", "未获取到可用 Cookie")

    config.dedao_cookie = cookie
    config.save()

    try:
        client = DedaoClient(cookie=cookie, debug=ctx.obj.get("debug", False))
        info = client.get_user_info()
    except DedaoAPIError as exc:
        _fail(ctx, "cookie_verify_failed", "Cookie 验证失败", str(exc))
        return

    _echo(
        ctx,
        {
            "ok": True,
            "message": "登录成功",
            "user": info,
        },
    )


@cli.command("list-courses")
@click.option("--category", "-c", default="all", help="分类：all/bauhinia/odob/ebook/compass")
@click.option("--limit", "-n", default=20, type=int, help="显示数量，0 表示全部")
@click.pass_context
def list_courses(ctx: click.Context, category: str, limit: int):
    """列出已购课程。"""
    cookie = _resolve_cookie(ctx)

    try:
        client = DedaoClient(cookie=cookie, debug=ctx.obj.get("debug", False))
        courses = client.get_course_list_all(category=category)
    except DedaoAPIError as exc:
        _fail(ctx, "list_courses_failed", "获取课程失败", str(exc))
        return

    if limit > 0:
        courses = courses[:limit]

    payload = {
        "ok": True,
        "count": len(courses),
        "courses": [
            {
                "id": course.id,
                "title": course.title,
                "author": course.author,
                "chapter_count": course.chapter_count,
                "category": course.category,
            }
            for course in courses
        ],
    }
    _echo(ctx, payload)


@cli.command("cat")
@click.pass_context
def show_categories(ctx: click.Context):
    """显示课程分类。"""
    _echo(
        ctx,
        {
            "categories": [
                {"id": "all", "desc": "全部课程"},
                {"id": "bauhinia", "desc": "专栏课程"},
                {"id": "odob", "desc": "有声书"},
                {"id": "ebook", "desc": "电子书"},
                {"id": "compass", "desc": "其他"},
            ]
        },
    )


@cli.command()
@click.argument("course_id")
@click.option("--output", "-o", type=click.Path(), default="", help="输出目录；默认使用配置中的 download_dir")
@click.option("--audio/--no-audio", default=None, help="是否下载音频")
@click.option("--format", "-f", type=click.Choice(["md", "pdf"]), default="md", help="输出格式")
@click.option("--workers", "-w", type=int, default=None, help="并发数，默认使用配置值")
@click.option("--concurrent/--serial", default=True, help="是否并发下载章节")
@click.pass_context
def download(
    ctx: click.Context,
    course_id: str,
    output: str,
    audio: Optional[bool],
    format: str,
    workers: Optional[int],
    concurrent: bool,
):
    """下载课程。"""
    cookie = _resolve_cookie(ctx)
    config = get_config()

    include_audio = config.download_audio if audio is None else audio
    max_workers = workers or config.max_workers
    output_dir = Path(output) if output else Path(config.download_dir)

    try:
        client = DedaoClient(cookie=cookie, debug=ctx.obj.get("debug", False))
        downloader = CourseDownloader(client=client, max_workers=max_workers, output_dir=output_dir)
        results = downloader.download_course(
            course_id=course_id,
            include_audio=include_audio,
            output_format=format,
            concurrent=concurrent,
        )
    except DedaoAPIError as exc:
        _fail(ctx, "download_failed", "下载失败", str(exc))
        return
    except Exception as exc:
        _fail(ctx, "download_failed", "下载失败", str(exc))
        return

    success = [result for result in results if result.success]
    failed = [result for result in results if not result.success]
    payload = {
        "ok": len(failed) == 0,
        "course_id": course_id,
        "downloaded": len(success),
        "failed": len(failed),
        "failures": [
            {
                "chapter_id": result.chapter.id if result.chapter else "",
                "title": result.chapter.title if result.chapter else "",
                "error": result.error,
            }
            for result in failed
        ],
    }
    _echo(ctx, payload)


@cli.command("sync-course")
@click.argument("course_id")
@click.option("--output", "-o", type=click.Path(), default="", help="输出目录；默认使用配置中的 download_dir")
@click.option("--audio/--no-audio", default=False, help="是否下载音频")
@click.option("--format", "-f", type=click.Choice(["md", "pdf"]), default="md", help="输出格式")
@click.option("--workers", "-w", type=int, default=None, help="并发数，默认使用配置值")
@click.option("--upload", is_flag=True, help="同步后上传到 NotebookLM")
@click.option("--notebook-id", default="", help="上传到指定 Notebook ID")
@click.option("--headful", is_flag=True, help="上传时显示浏览器窗口")
@click.pass_context
def sync_course(
    ctx: click.Context,
    course_id: str,
    output: str,
    audio: bool,
    format: str,
    workers: Optional[int],
    upload: bool,
    notebook_id: str,
    headful: bool,
):
    """一键同步课程：增量下载、合并、导出 AI pack，并可选上传 NotebookLM。"""
    cookie = _resolve_cookie(ctx)
    config = get_config()
    max_workers = workers or config.max_workers

    try:
        client = DedaoClient(cookie=cookie, debug=ctx.obj.get("debug", False))
        service = CourseSyncService(
            client=client,
            output_root=Path(output) if output else Path(config.download_dir),
            workers=max_workers,
        )
        result = service.sync_course(
            course_id=course_id,
            include_audio=audio,
            output_format=format,
            upload_to_notebooklm=upload,
            notebook_id=notebook_id or None,
            headless=not headful,
        )
    except Exception as exc:
        _fail(ctx, "sync_failed", "课程同步失败", str(exc))
        return

    _echo(
        ctx,
        {
            "ok": result.failed == 0,
            "course_id": result.course_id,
            "course_title": result.course_title,
            "course_dir": str(result.course_dir),
            "manifest": str(result.manifest_path),
            "chapter_state": str(result.chapter_state_path),
            "downloaded": result.downloaded,
            "skipped": result.skipped,
            "failed": result.failed,
            "uploaded_files": result.uploaded_files,
            "notebook_id": result.notebook_id,
            "notebook_url": result.notebook_url,
            "ai_pack": result.ai_pack,
        },
    )


@cli.command("course-ppts")
@click.argument("course_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--storage",
    default="",
    type=click.Path(dir_okay=False),
    help="NotebookLM storage_state.json 路径；默认自动选择最近一次登录态",
)
@click.option("--notebook-title", default="", help="Notebook 标题，默认使用课程目录名")
@click.option("--prompt", default=DEFAULT_PROMPT, help="生成 PPT 的提示词")
@click.option("--language", default=DEFAULT_LANGUAGE, help="NotebookLM 输出语言代码")
@click.option("--output", "-o", type=click.Path(), default="", help="PPT 输出目录；默认使用配置中的 ppt_dir")
@click.option("--force", is_flag=True, help="即使已存在也重新生成")
@click.option(
    "--exclude",
    multiple=True,
    help="可重复指定排除关键词；默认排除 发刊词 / 特别放送 / 问答",
)
@click.pass_context
def course_ppts_cmd(
    ctx: click.Context,
    course_dir: str,
    storage: str,
    notebook_title: str,
    prompt: str,
    language: str,
    output: str,
    force: bool,
    exclude: tuple[str, ...],
):
    """将课程章节上传到 NotebookLM 并生成中文 PPTX。"""
    exclude_keywords = exclude or DEFAULT_EXCLUDE_KEYWORDS

    try:
        manifest = run_course_ppts(
            course_dir,
            storage=storage or None,
            notebook_title=notebook_title,
            prompt=prompt,
            language=language,
            output_dir=output or None,
            force=force,
            exclude_keywords=exclude_keywords,
        )
    except Exception as exc:
        _fail(ctx, "course_ppts_failed", "课程 PPT 生成失败", str(exc))
        return

    _echo(
        ctx,
        {
            "ok": True,
            "course_dir": manifest["course_dir"],
            "storage_path": manifest["storage_path"],
            "notebook_id": manifest["notebook_id"],
            "notebook_title": manifest["notebook_title"],
            "output_dir": manifest["output_dir"],
            "manifest": manifest["manifest_path"],
            "generated_count": manifest["generated_count"],
            "exclude_keywords": manifest["exclude_keywords"],
            "items": [
                {
                    "source_title": item["source_title"],
                    "output_path": item["output_path"],
                    "status": item["generation"]["status"],
                }
                for item in manifest["items"]
            ],
        },
    )


@cli.command("export-ai-pack")
@click.argument("course_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--course-id", default="unknown", help="课程 ID")
@click.option("--course-title", default="", help="课程标题，默认使用目录名")
@click.option("--output", type=click.Path(), default="", help="输出目录，默认 <course_dir>/ai_pack")
@click.option("--target-tokens", type=int, default=900, help="目标 chunk token 数")
@click.option("--overlap-tokens", type=int, default=100, help="chunk overlap token 数")
@click.pass_context
def export_ai_pack_cmd(
    ctx: click.Context,
    course_dir: str,
    course_id: str,
    course_title: str,
    output: str,
    target_tokens: int,
    overlap_tokens: int,
):
    """从已下载课程目录导出 AI pack。"""
    base_dir = Path(course_dir)
    title = course_title or base_dir.name
    out_dir = Path(output) if output else base_dir / "ai_pack"

    chapter_files = []
    for path in sorted(base_dir.glob("*.md")):
        if path.name in {"full.md", "brief.md", "merged.md"}:
            continue
        match = re.match(r"^(\d+)_", path.name)
        order = int(match.group(1)) if match else 999999
        chapter_files.append(
            ChapterSource(
                chapter_id=path.stem,
                title=path.stem,
                order=order,
                path=path,
            )
        )

    if not chapter_files:
        _fail(ctx, "no_chapters", "未找到可导出的 Markdown 章节文件")

    files = export_ai_pack(
        course_id=course_id,
        course_title=title,
        chapter_sources=chapter_files,
        output_dir=out_dir,
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
    )
    _echo(ctx, {"ok": True, "course_id": course_id, "course_title": title, "files": files})


@cli.command("query-ai-pack")
@click.argument("pack_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--query", "-q", required=True, help="查询问题")
@click.option("--top-k", type=int, default=6, help="最多返回 chunk 数")
@click.option("--hard-budget-tokens", type=int, default=6000, help="上下文 token 硬预算")
@click.pass_context
def query_ai_pack_cmd(
    ctx: click.Context,
    pack_dir: str,
    query: str,
    top_k: int,
    hard_budget_tokens: int,
):
    """从 AI pack 中按预算构建问答上下文。"""
    context = build_query_context(
        query=query,
        pack_dir=Path(pack_dir),
        top_k=top_k,
        hard_budget_tokens=hard_budget_tokens,
    )
    _echo(
        ctx,
        {
            "ok": True,
            "mode": context["mode"],
            "selected_count": len(context.get("selected", [])),
            "context": context["text"],
        },
    )


@cli.command("migrate-data")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    show_default=True,
    help="项目根目录；会把其中的 downloads/ 和 ppts/ 迁移到配置中的外置数据目录",
)
@click.option("--dry-run", is_flag=True, help="只显示计划，不执行迁移")
@click.pass_context
def migrate_data_cmd(ctx: click.Context, project_root: str, dry_run: bool):
    """把仓库内数据迁移到仓库外，并重写相关 manifest 路径。"""
    config = get_config()
    try:
        result = migrate_project_data(
            project_root=Path(project_root),
            download_root=Path(config.download_dir),
            ppt_root=Path(config.ppt_dir),
            dry_run=dry_run,
        )
    except Exception as exc:
        _fail(ctx, "migrate_failed", "数据迁移失败", str(exc))
        return

    _echo(ctx, {"ok": True, **result})


@cli.command()
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str):
    """设置配置项。"""
    config = get_config()

    if not hasattr(config, key):
        _fail(ctx, "unknown_config_key", f"未知配置项: {key}")

    cast_value: Any = value
    current = getattr(config, key)
    if isinstance(current, bool):
        cast_value = value.lower() in {"1", "true", "yes", "on"}
    elif isinstance(current, int):
        cast_value = int(value)

    setattr(config, key, cast_value)
    config.save()
    _echo(ctx, {"ok": True, "key": key, "value": cast_value})


@cli.command()
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str):
    """获取配置项。"""
    config = get_config()
    if not hasattr(config, key):
        _fail(ctx, "unknown_config_key", f"未知配置项: {key}")
    _echo(ctx, {"ok": True, "key": key, "value": getattr(config, key)})


@cli.command()
@click.pass_context
def config_list(ctx: click.Context):
    """列出全部配置。"""
    config = get_config()
    _echo(
        ctx,
        {
            "ok": True,
            "config": {
                "download_dir": config.download_dir,
                "ppt_dir": config.ppt_dir,
                "max_workers": config.max_workers,
                "download_audio": config.download_audio,
                "generate_pdf": config.generate_pdf,
                "log_level": config.log_level,
                "dedao_cookie_set": bool(config.dedao_cookie),
            },
        },
    )


def main() -> None:
    _configure_stdio()
    cli()


if __name__ == "__main__":
    main()
