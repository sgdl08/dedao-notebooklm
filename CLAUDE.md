# CLAUDE.md

本仓库是一个“得到课程 -> NotebookLM -> AI pack / PPT”工具链。

## 关键约束

- 代码在仓库内，数据默认在仓库外
- 默认数据根：`~/Documents/dedao-notebooklm-data`
- 默认课程目录：`~/Documents/dedao-notebooklm-data/downloads`
- 默认 PPT 目录：`~/Documents/dedao-notebooklm-data/ppts`
- 不要把下载内容、PPT、Cookie 等数据提交到 Git

## 优先入口

优先使用稳定 CLI，而不是直接拼内部模块：

```bash
dedao-nb --json list-courses
dedao-nb --json download <COURSE_ID>
dedao-nb --json sync-course <COURSE_ID>
dedao-nb --json course-ppts "<COURSE_DIR>"
dedao-nb --json migrate-data --project-root .
```

API 入口：

```bash
dedao-api
```

## 常用开发命令

```bash
python -m pip install -e .
python -m pip install -e ".[dev]"
python -m pytest -q
python -m compileall -q src
python -m ruff check src
python -m black src
```

## 目录理解

- `src/cli.py`: 主 CLI
- `src/course_sync.py`: 课程同步主流程
- `src/course_ppts.py`: NotebookLM 章节 PPT 工作流
- `src/data_migration.py`: 仓库内数据迁移到仓库外
- `skills/dedao-notebooklm/SKILL.md`: 给 Codex / Claude / OpenClaw 用的 skill 入口

## 修改策略

- 涉及路径时，优先通过 `utils.config.get_config()` 读取配置
- 新功能尽量先落 CLI，再补 README / skill
- 若要处理旧项目目录中的 `downloads/` 或 `ppts/`，优先走 `dedao-nb migrate-data`
