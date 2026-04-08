# dedao-notebooklm

下载得到已购课程与电子书，并导出为 Markdown、HTML、EPUB 的命令行工具。仓库中还保留了若干 NotebookLM 相关辅助脚本，位于 extras 目录。

## 当前能力

- 下载已购课程正文，支持 Markdown、HTML、TXT 输出
- 按需下载课程音频
- 下载已购电子书，支持 Markdown、HTML、EPUB 输出
- 将电子书 SVG 页面转换为结构化 Markdown / NotebookLM HTML
- 本地保存登录 Cookie，默认写入用户目录而不是仓库目录

## 安装

```bash
git clone https://github.com/sgdl08/dedao-notebooklm.git
cd dedao-notebooklm
python3 -m pip install -e .
```

开发环境：

```bash
python3 -m pip install -e ".[dev]"
```

## 登录

先从浏览器开发者工具中获取得到站点请求头里的 Cookie，然后执行：

```bash
dedao-nb login --cookie "your-cookie"
```

当前 CLI 保留了 `--qrcode` 参数，但实现尚未启用；公开使用时应以 Cookie 登录为准。

## 常用命令

```bash
# 列出已购课程
dedao-nb list-courses --limit 20

# 下载课程正文
dedao-nb download <COURSE_ID> --format md

# 下载课程并附带音频
dedao-nb download <COURSE_ID> --audio --format md

# 下载电子书，参数可传 ID、enid 或标题
dedao-nb download-ebook "<EBOOK_ID_OR_TITLE>" --format md

# 查看当前配置
dedao-nb config-list
```

## 配置与安全

默认配置文件路径：`~/.dedao-notebooklm/config.json`

示例：

```json
{
  "dedao_cookie": "your-dedao-cookie",
  "download_dir": "./downloads",
  "max_workers": 5
}
```

仓库中的 `downloads/`、`outputs/`、`config.json`、`.env` 等目录或文件已在 `.gitignore` 中排除，避免把下载产物和本地凭据直接提交到 Git。

## 项目结构

```text
dedao-notebooklm/
├── src/
│   ├── cli.py
│   ├── converter/      # HTML / SVG / EPUB 转换
│   ├── dedao/          # API 客户端、认证、缓存、课程/电子书下载
│   ├── merger/         # 专栏合并工具
│   └── utils/          # 配置、浏览器、ffmpeg 等工具
├── extras/             # NotebookLM 相关辅助脚本
├── scripts/            # 批量下载与自愈脚本
└── tests/
```

## 开发

```bash
python3 -m pytest tests/ -v
python3 -m black src/
python3 -m ruff check src/
```

## 使用边界

1. 得到 API 属于非公开接口，站点更新可能导致功能失效。
2. Cookie 属于敏感凭据，应仅保存在本机，必要时及时轮换。
3. 下载内容应仅用于个人学习，请遵守版权与平台使用条款。

## 许可证状态

当前仓库尚未附带 LICENSE 文件。若要以开源方式对外分发，请先补充明确的许可证文本。
