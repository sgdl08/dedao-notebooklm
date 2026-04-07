# dedao-downloader

下载 [得到](https://www.dedao.cn) 专栏课程的工具。

## 功能特性

- 📚 下载已购专栏课程（文字内容）
- 🎧 支持下载音频文件（可选）
- 📝 自动转换 HTML 为 Markdown 格式
- ⚡ 支持并发下载
- 🔐 本地保存认证信息

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/your-username/dedao-notebooklm.git
cd dedao-notebooklm

# 安装依赖
pip install -r requirements.txt

# 或者使用 pyproject.toml 安装
pip install -e .
```

### 获取 Cookie

1. 访问 [https://www.dedao.cn](https://www.dedao.cn) 并登录
2. 按 `F12` 打开开发者工具
3. 切换到 **Network** 标签
4. 刷新页面
5. 点击任意 API 请求
6. 在 **Request Headers** 中找到 `Cookie` 值并复制

### 使用

```bash
# 登录得到
dedao-nb login

# 列出已购课程
dedao-nb list-courses

# 下载课程
dedao-nb download <COURSE_ID>

# 下载课程到指定目录
dedao-nb download <COURSE_ID> -o ./my-courses

# 下载时不包含音频
dedao-nb download <COURSE_ID> --no-audio
```

## 命令行帮助

```
Usage: dedao-nb [OPTIONS] COMMAND [ARGS]...

  得到课程下载工具

Options:
  -c, --config PATH  配置文件路径
  -v, --verbose      显示详细日志
  --help             显示帮助信息

Commands:
  login           登录得到网站
  list-courses    列出已购课程
  download        下载课程到本地
  config-set      设置配置项
  config-get      获取配置项
  config-list     列出所有配置
```

## 项目结构

```
dedao-notebooklm/
├── src/
│   ├── cli.py                 # 命令行入口
│   ├── dedao/
│   │   ├── __init__.py
│   │   ├── auth.py            # 认证模块
│   │   ├── client.py          # 得到 API 客户端
│   │   ├── models.py          # 数据模型
│   │   └── downloader.py      # 下载器
│   ├── converter/
│   │   ├── __init__.py
│   │   └── html_to_md.py      # HTML 转 Markdown
│   └── utils/
│       ├── __init__.py
│       └── config.py          # 配置管理
├── tests/
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 配置

配置文件位于 `~/.dedao-notebooklm/config.json`

```json
{
  "dedao_cookie": "your-dedao-cookie",
  "download_dir": "./downloads",
  "max_workers": 5,
  "download_audio": true,
  "log_level": "INFO"
}
```

## 输出格式

下载的课程将保存到以下结构：

```
downloads/
└── 课程标题/
    ├── 001_第一章标题.md
    ├── 002_第二章标题.md
    ├── 003_第三章标题.mp3
    └── ...
```

## 注意事项

1. **API 稳定性**: 得到 API 是非公开的，可能随网站更新而变化
2. **Cookie 安全**: 请妥善保管 Cookie，不要泄露给他人
3. **版权**: 下载的内容仅供个人学习使用，请勿传播

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
black src/
ruff check src/
```

## 依赖

- `requests` - HTTP 请求
- `click` - 命令行框架
- `beautifulsoup4` - HTML 解析
- `markdown` - Markdown 处理
- `PyYAML` - YAML 支持

## 许可证

MIT License

## 免责声明

本工具仅供学习交流使用，请支持正版内容。使用本工具下载的内容请遵守相关法律法规和使用条款。
