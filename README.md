# dedao-notebooklm

[![CI](https://github.com/sgdl08/dedao-notebooklm/actions/workflows/ci.yml/badge.svg)](https://github.com/sgdl08/dedao-notebooklm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

下载你已购买的得到课程，整理为 Markdown / AI pack，同步到 NotebookLM，并为章节生成中文演讲稿 PPT。

这个仓库面向三类使用方式：

- 命令行：`dedao-nb`
- API：`dedao-api`
- Agent / skill：仓库内置 [skills/dedao-notebooklm/SKILL.md](skills/dedao-notebooklm/SKILL.md)，可给 Codex、Claude Code、OpenClaw 作为稳定调用入口

## 项目目标

- 课程下载、增量同步、AI pack 导出
- NotebookLM 上传与课程章节 PPT 生成
- 数据默认存放在仓库外，便于 GitHub 开源协作和跨设备维护
- CLI 输出支持 `--json`，便于被自动化工具调用

## 使用边界

- 只适用于你已购买、已授权或已合法导出的内容
- 仓库提供整理、同步、导出、PPT 生成能力，不提供破解、绕过鉴权或盗版下载能力
- 默认把课程数据和生成产物放在仓库外，避免误提交到 Git

## 快速开始

```bash
git clone https://github.com/sgdl08/dedao-notebooklm.git
cd dedao-notebooklm
python -m pip install -e .
dedao-nb login --qrcode
dedao-nb list-courses -n 20
dedao-nb sync-course <COURSE_ID>
```

## 默认目录设计

代码留在仓库内，数据留在仓库外。

- 仓库代码：当前目录
- 默认数据根：
  Windows: `~/Documents/dedao-notebooklm-data`
  macOS: `~/Documents/dedao-notebooklm-data`
- 默认课程目录：`~/Documents/dedao-notebooklm-data/downloads`
- 默认 PPT 目录：`~/Documents/dedao-notebooklm-data/ppts`

这样做有两个目的：

- 避免把大体积课程内容和生成产物提交到 GitHub
- 让你在 Windows 和 Mac 上切换时，仓库结构保持干净一致

## 安装

```bash
git clone https://github.com/sgdl08/dedao-notebooklm.git
cd dedao-notebooklm
python -m pip install -e .
```

开发模式：

```bash
python -m pip install -e ".[dev]"
```

## 登录

```bash
# 手动提供 Cookie
dedao-nb login --cookie "<your-dedao-cookie>"

# 或使用二维码登录
dedao-nb login --qrcode
```

配置文件位于：

```text
~/.dedao-notebooklm/config.json
```

示例：

```json
{
  "dedao_cookie": "",
  "download_dir": "C:/Users/<YOU>/Documents/dedao-notebooklm-data/downloads",
  "ppt_dir": "C:/Users/<YOU>/Documents/dedao-notebooklm-data/ppts",
  "max_workers": 5,
  "download_audio": true,
  "generate_pdf": false,
  "log_level": "INFO"
}
```

## 常用命令

列出课程：

```bash
dedao-nb list-courses -n 20
```

下载课程：

```bash
dedao-nb download <COURSE_ID>
dedao-nb download <COURSE_ID> --no-audio --format md
```

一键同步课程：

```bash
dedao-nb sync-course <COURSE_ID>
dedao-nb sync-course <COURSE_ID> --upload --notebook-id <NOTEBOOK_ID>
```

导出 AI pack：

```bash
dedao-nb export-ai-pack "<COURSE_DIR>" --course-id <COURSE_ID>
```

基于 AI pack 构建问答上下文：

```bash
dedao-nb query-ai-pack "<COURSE_DIR>/ai_pack" -q "这门课讲了什么"
```

为课程章节生成中文 PPT：

```bash
dedao-nb course-ppts "<COURSE_DIR>"
dedao-nb course-ppts "<COURSE_DIR>" --force
```

把仓库内旧数据迁移到仓库外：

```bash
dedao-nb migrate-data --project-root .
```

JSON 输出模式：

```bash
dedao-nb --json sync-course <COURSE_ID>
dedao-nb --json course-ppts "<COURSE_DIR>"
```

## 辅助脚本

NotebookLM 相关脚本放在 `scripts/notebooklm/`：

```bash
python scripts/notebooklm/list_notebooks.py
python scripts/notebooklm/fetch_notebooks.py -o notebooks_list.md
python scripts/notebooklm/notebook_manager.py refresh
python scripts/notebooklm/upload_files.py "<COURSE_DIR>" --notebook-id <NOTEBOOK_ID>
python scripts/notebooklm/create_and_upload.py "<NOTEBOOK_TITLE>" "<COURSE_DIR>"
python scripts/notebooklm/notebooklm_course_ppts.py "<COURSE_DIR>"
```

维护性脚本放在 `scripts/maintenance/`：

```bash
python scripts/maintenance/batch_download.py
python scripts/maintenance/redownload.py
python scripts/maintenance/rename_md_files.py
python scripts/maintenance/rename_folders.py
```

## API

启动服务：

```bash
dedao-api
```

接口：

- `GET /health`
- `POST /courses/sync`
- `GET /courses/{course_id}/manifest`
- `POST /notebooks/upload`

## Skill / Agent 集成

仓库包含一个可安装的 skill：

- [skills/dedao-notebooklm/SKILL.md](skills/dedao-notebooklm/SKILL.md)

建议给 agent 的稳定调用方式：

- 读配置：`dedao-nb config-list`
- 下载课程：`dedao-nb --json download <COURSE_ID>`
- 同步课程：`dedao-nb --json sync-course <COURSE_ID>`
- 生成 PPT：`dedao-nb --json course-ppts "<COURSE_DIR>"`
- 迁移数据：`dedao-nb --json migrate-data --project-root .`

OpenClaw / Codex / Claude Code 都应优先调用 CLI，而不是直接操作内部模块。

## 开发

```bash
python -m pytest -q
python -m compileall -q src
python -m ruff check src
python -m black src
```

## 迁移旧项目数据

如果你的仓库根目录里已经有旧的 `downloads/` 或 `ppts/`：

1. 先确认 `config.json` 里的 `download_dir` / `ppt_dir`
2. 运行 `dedao-nb migrate-data --project-root .`
3. 迁移命令会移动目录，并重写 manifest / state 中的旧路径

## 许可证

MIT
