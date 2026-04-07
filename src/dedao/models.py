"""得到 (Dedao) 数据模型"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ==================== 课程相关 ====================

@dataclass
class Course:
    """课程模型"""
    id: str
    title: str
    cover: str = ""
    author: str = ""
    description: str = ""
    chapter_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 额外信息
    price: Optional[float] = None
    is_finished: bool = False
    category: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Chapter:
    """章节模型"""
    id: str
    course_id: str
    title: str
    sort_order: int = 0
    content: str = ""  # HTML 内容
    audio_url: Optional[str] = None
    audio_duration: Optional[int] = None  # 秒
    created_at: Optional[datetime] = None

    # 下载状态
    downloaded: bool = False
    local_path: Optional[str] = None

    # 额外信息
    is_free: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CourseDetail:
    """课程详情（包含章节列表）"""
    course: Course
    chapters: List[Chapter] = field(default_factory=list)

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    @property
    def has_audio(self) -> bool:
        return any(chapter.audio_url for chapter in self.chapters)


# ==================== 有声书相关 ====================

@dataclass
class Audiobook:
    """有声书模型"""
    alias_id: str  # 有声书别名 ID
    title: str
    cover: str = ""
    author: str = ""  # 作者/主讲人
    reader: str = ""  # 朗读者
    duration: int = 0  # 总时长（秒）
    mp3_url: str = ""  # 音频 URL
    summary: str = ""  # 简介
    is_vip: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudiobookChapter:
    """有声书章节"""
    id: str
    title: str
    sort_order: int = 0
    audio_url: str = ""
    duration: int = 0  # 秒
    content: str = ""  # 文字内容（如果有）
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudiobookDetail:
    """有声书详情"""
    audiobook: Audiobook
    chapters: List[AudiobookChapter] = field(default_factory=list)

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    @property
    def total_duration(self) -> int:
        """总时长（秒）"""
        return sum(ch.duration for ch in self.chapters) or self.audiobook.duration


# ==================== 电子书相关 ====================

@dataclass
class EbookCatalog:
    """电子书目录项"""
    chapter_id: str
    title: str
    level: int = 0  # 目录层级
    order: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EbookDetail:
    """电子书详情"""
    enid: str  # 电子书 ID
    title: str
    cover: str = ""
    author: str = ""
    author_info: str = ""  # 作者简介
    book_intro: str = ""  # 书籍简介
    publish_time: str = ""
    is_vip_book: bool = False
    price: Optional[float] = None
    catalog: List[EbookCatalog] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EbookChapter:
    """电子书章节（包含 SVG 内容）"""
    chapter_id: str
    title: str
    order: int = 0
    svg_contents: List[str] = field(default_factory=list)  # SVG 内容列表
    html_content: str = ""  # 转换后的 HTML
    markdown_content: str = ""  # 转换后的 Markdown
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EbookPage:
    """电子书页面"""
    page_id: str
    svg: str  # 加密的 SVG 内容
    chapter_id: str = ""


@dataclass
class EbookInfo:
    """电子书阅读信息"""
    token: str = ""
    toc: List[EbookCatalog] = field(default_factory=list)
    orders: List[Dict[str, Any]] = field(default_factory=list)  # 章节顺序
    pages: List[EbookPage] = field(default_factory=list)


# ==================== 频道/学习圈相关 ====================

@dataclass
class ChannelPerson:
    """频道人物"""
    uid: str
    name: str
    avatar: str = ""
    title: str = ""


@dataclass
class ChannelStatistics:
    """频道统计"""
    member_count: int = 0
    note_count: int = 0
    view_count: int = 0


@dataclass
class ChannelInfo:
    """频道/学习圈信息"""
    channel_id: str
    title: str
    description: str = ""
    logo: str = ""
    host: Optional[ChannelPerson] = None
    statistics: Optional[ChannelStatistics] = None
    is_vip: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelCategory:
    """频道分类"""
    id: str
    name: str
    description: str = ""
    note_count: int = 0


@dataclass
class ChannelNote:
    """频道笔记"""
    id: str
    title: str
    content: str = ""
    author: Optional[ChannelPerson] = None
    created_at: str = ""
    like_count: int = 0
    comment_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelHomepage:
    """频道首页"""
    channel: ChannelInfo
    categories: List[ChannelCategory] = field(default_factory=list)
    featured_notes: List[ChannelNote] = field(default_factory=list)


# ==================== 主题/社区相关 ====================

@dataclass
class Topic:
    """主题"""
    id: str
    title: str
    description: str = ""
    cover: str = ""
    note_count: int = 0
    participant_count: int = 0
    is_hot: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TopicNote:
    """主题笔记"""
    id: str
    title: str
    content: str = ""
    author: Optional[ChannelPerson] = None
    created_at: str = ""
    like_count: int = 0
    comment_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TopicDetail:
    """主题详情"""
    topic: Topic
    notes: List[TopicNote] = field(default_factory=list)

    @property
    def total_notes(self) -> int:
        return len(self.notes)


# ==================== 通用资源 ====================

@dataclass
class ContentCategory:
    """内容分类"""
    id: str
    name: str
    type: str = ""  # course, audiobook, ebook, ace
    icon: str = ""
    description: str = ""


@dataclass
class FreeContent:
    """免费内容"""
    id: str
    title: str
    type: str  # course, audiobook, ebook
    cover: str = ""
    description: str = ""
    author: str = ""
    url: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)
