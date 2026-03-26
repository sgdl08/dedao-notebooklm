# 贡献指南

## 开发原则

- 先保证 CLI 契约稳定，再扩内部实现
- 数据默认放仓库外，不要把 `downloads/`、`ppts/`、Cookie、浏览器登录态提交到仓库
- 新功能如果会被 agent 调用，优先补 `--json` 输出

## 本地环境

```bash
python -m pip install -e ".[dev]"
```

## 提交前检查

```bash
python -m pytest -q
python -m compileall -q src
python -m ruff check src
```

## 路径与数据

- 默认数据根：`~/Documents/dedao-notebooklm-data`
- 默认课程目录：`~/Documents/dedao-notebooklm-data/downloads`
- 默认 PPT 目录：`~/Documents/dedao-notebooklm-data/ppts`

如果你手上已有旧仓库内数据，先执行：

```bash
dedao-nb migrate-data --project-root .
```

## Skill 约定

如果修改了 CLI 或 API 的调用方式，同步更新：

- `README.md`
- `CLAUDE.md`
- `skills/dedao-notebooklm/SKILL.md`
