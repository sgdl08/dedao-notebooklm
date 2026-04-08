"""得到课程下载工具 - 命令行接口

下载得到专栏课程到本地。
"""

import logging
import sys
from pathlib import Path
from typing import Optional, List

import click

from dedao import DedaoAPIError, DedaoClient, EbookDownloader
from dedao.course import CourseDownloader
from converter import HTMLToMarkdownConverter
from utils import get_config, load_config, Config
from merger import ArticleMerger

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@click.group()
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, dir_okay=False),
    help='配置文件路径',
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='显示详细日志',
)
@click.option(
    '--debug',
    is_flag=True,
    help='调试模式（打印原始 API 返回）',
)
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool, debug: bool):
    """得到课程下载工具

    下载得到专栏课程到本地。
    """
    # 加载配置
    if config:
        load_config(Path(config))
    else:
        load_config()

    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option('--cookie', '-k', help='Cookie 字符串')
@click.option('--qrcode', '-q', is_flag=True, help='使用二维码登录')
@click.pass_context
def login(ctx, cookie: str, qrcode: bool):
    """登录得到账户

    使用 Cookie 或二维码登录。
    """
    config = get_config()

    if cookie:
        # 使用 Cookie 登录
        config.dedao_cookie = cookie
        config.save()
        click.echo("✓ Cookie 已保存")

        # 验证 Cookie
        try:
            client = DedaoClient(cookie=cookie)
            user_info = client.get_user_info()
            click.echo(f"✓ 登录成功: {user_info.get('nick_name', '未知用户')}")
        except DedaoAPIError as e:
            click.echo(f"✗ Cookie 验证失败: {e}", err=True)
            sys.exit(1)

    elif qrcode:
        click.echo("当前版本暂不支持二维码登录，请使用 --cookie 登录", err=True)
        sys.exit(1)

    else:
        click.echo("请使用 --cookie 或 --qrcode 参数登录")
        sys.exit(1)


@cli.command('list-courses')
@click.option('--category', '-c', default='all', help='分类：all/bauhinia/odob/ebook/compass')
@click.option('--limit', '-n', default=20, help='显示数量（0=全部）')
@click.pass_context
def list_courses(ctx, category: str, limit: int):
    """列出已购课程"""
    config = get_config()

    if not config.dedao_cookie:
        click.echo("请先登录: dedao-nb login --cookie <cookie>", err=True)
        sys.exit(1)

    try:
        client = DedaoClient(cookie=config.dedao_cookie)

        courses = client.get_all_courses()

        if category != 'all':
            # 可以添加分类过滤
            pass

        if limit > 0:
            courses = courses[:limit]

        if not courses:
            click.echo("没有找到课程")
            return

        click.echo(f"\n找到 {len(courses)} 门课程:\n")

        for i, course in enumerate(courses, 1):
            click.echo(f"{i}. {course.title}")
            click.echo(f"   ID: {course.id}")
            if hasattr(course, 'chapter_count'):
                click.echo(f"   章节: {course.chapter_count}")
            click.echo()

    except DedaoAPIError as e:
        click.echo(f"获取课程失败: {e}", err=True)
        sys.exit(1)


@cli.command('cat')
@click.pass_context
def show_categories(ctx):
    """显示课程分类"""
    click.echo("""
课程分类:
  all      - 全部课程
  bauhinia  - 专栏课程
  odob      - 电子书
  ebook     - 电子书（别名）
  compass   - 其他
""")


@cli.command()
@click.argument('course_id')
@click.option(
    '--output', '-o',
    type=click.Path(),
    default='./downloads',
    help='输出目录'
)
@click.option(
    '--audio',
    is_flag=True,
    help='同时下载音频'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['md', 'html', 'txt']),
    default='md',
    help='输出格式'
)
@click.pass_context
def download(ctx, course_id: str, output: str, audio: bool, format: str):
    """下载课程

    下载指定课程的所有章节。
    """
    config = get_config()

    if not config.dedao_cookie:
        click.echo("请先登录: dedao-nb login --cookie <cookie>", err=True)
        sys.exit(1)

    output_dir = Path(output)

    try:
        client = DedaoClient(cookie=config.dedao_cookie)

        # 获取课程信息
        click.echo(f"获取课程信息: {course_id}...")
        course = client.get_course_detail(course_id)

        if not course:
            click.echo(f"课程不存在: {course_id}", err=True)
            sys.exit(1)

        click.echo(f"课程: {course.title}")
        click.echo(f"章节: {len(course.chapters) if course.chapters else '未知'}")

        # 创建课程目录
        course_dir = output_dir / course.title.replace('/', '_')
        course_dir.mkdir(parents=True, exist_ok=True)

        # 下载章节
        if course.chapters:
            downloader = CourseDownloader(client, course_dir)
            downloader.download_chapters(course.chapters, format=format)

            if audio:
                click.echo("\n下载音频...")
                downloader.download_audios(course.chapters)

        click.echo(f"\n✓ 下载完成: {course_dir}")

    except DedaoAPIError as e:
        click.echo(f"下载失败: {e}", err=True)
        sys.exit(1)


@cli.command("download-ebook")
@click.argument("ebook_id_or_title")
@click.option(
    "--output", "-o",
    type=click.Path(),
    default="./downloads/ebooks",
    help="输出目录",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["md", "html", "epub"]),
    default="md",
    help="输出格式",
)
@click.pass_context
def download_ebook_cmd(ctx, ebook_id_or_title: str, output: str, format: str):
    """下载电子书。

    参数支持电子书 ID、enid 或标题。
    """
    config = get_config()

    if not config.dedao_cookie:
        click.echo("请先登录: dedao-nb login --cookie <cookie>", err=True)
        sys.exit(1)

    downloader = EbookDownloader(output_dir=Path(output))
    result = downloader.download(ebook_id_or_title, output_format=format)

    if not result.success:
        click.echo(f"下载失败: {result.error}", err=True)
        sys.exit(1)

    click.echo(f"✓ 下载完成: {result.ebook.title}")
    for output_file in result.output_files:
        click.echo(f"  - {output_file}")


# ==================== 配置管理 ====================

@cli.command()
@click.argument('key')
@click.argument('value')
@click.pass_context
def config_set(ctx, key: str, value: str):
    """设置配置项

    \b
    KEY: 配置项名称 (download_dir, max_workers 等)
    \b
    VALUE: 配置值
    """
    config = get_config()

    if hasattr(config, key):
        setattr(config, key, value)
        config.save()
        click.echo(f"✓ 已设置 {key} = {value}")
    else:
        click.echo(f"✗ 未知配置项: {key}", err=True)
        click.echo("可用配置项: download_dir, max_workers")
        sys.exit(1)


@cli.command()
@click.argument('key')
@click.pass_context
def config_get(ctx, key: str):
    """获取配置项"""
    config = get_config()

    if hasattr(config, key):
        value = getattr(config, key)
        click.echo(f"{key} = {value}")
    else:
        click.echo(f"✗ 未知配置项: {key}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def config_list(ctx):
    """列出所有配置"""
    config = get_config()

    click.echo("\n当前配置:")
    click.echo(f"  download_dir = {config.download_dir}")
    click.echo(f"  max_workers = {config.max_workers}")
    click.echo(f"  dedao_cookie = {'已设置' if config.dedao_cookie else '未设置'}")


def main():
    """入口点"""
    cli()


if __name__ == "__main__":
    main()
