"""常量定义

API 端点、分类常量、配置常量等。
"""

# API 基础 URL
DEDIAO_API_BASE = "https://www.dedao.cn"

# API 端点
class APIEndpoint:
    """API 端点常量"""

    # 课程相关
    COURSE_LIST = "/api/hades/v2/product/list"
    COURSE_GROUP_LIST = "/api/hades/v2/product/group/list"
    COURSE_DETAIL = "/pc/bauhinia/pc/class/info"
    ARTICLE_LIST = "/api/pc/bauhinia/pc/class/purchase/article_list"
    ARTICLE_INFO = "/pc/bauhinia/pc/article/info"
    ARTICLE_CONTENT = "/pc/ddarticle/v1/article/get/v2"

    # 电子书相关
    EBOOK_DETAIL = "/pc/ebook2/v1/pc/detail"
    EBOOK_READ_TOKEN = "/api/pc/ebook2/v1/pc/read/token"
    EBOOK_INFO = "/ebk_web/v1/get_book_info"
    EBOOK_PAGES = "/ebk_web_go/v2/get_pages"

    # 用户相关
    USER_INFO = "/api/pc/user/info"
    TOKEN_CREATE = "/ddph/v2/token/create"

    # 分类列表
    INDEX_DETAIL = "/api/hades/v1/index/detail"


# 内容分类
class ContentType:
    """内容类型常量"""

    ALL = "all"
    COURSE = "bauhinia"      # 专栏课程
    AUDIOBOOK = "odob"       # 有声书/每天听本书
    EBOOK = "ebook"          # 电子书
    ACE = "compass"          # 锦囊

    # 别名映射
    ALIASES = {
        "course": "bauhinia",
        "audiobook": "odob",
        "book": "odob",
    }


# AES 加密常量（电子书解密）
AES_KEY = "3e4r06tjkpjcevlbslr3d96gdb5ahbmo"
AES_IV = "6fd89a1b3a7f48fb"

# dedao-dl 工具配置
DEDAO_DL_PATH = "~/go/bin/dedao-dl"
DEDAO_DL_CONFIG_PATH = "~/.dedao/config.json"

# 默认配置
DEFAULT_CONFIG = {
    "download_dir": "./downloads",
    "max_workers": 5,
    "request_timeout": 30,
    "cache_ttl": 86400,  # 24 小时
}
