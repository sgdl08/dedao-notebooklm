# 重构计划：dedao-notebooklm

## 目标
1. 架构清晰化：按内容类型拆分模块 ✅
2. 集成 dedao-dl：使用 Go 工具作为主要下载器 ✅
3. 移除 playwright：删除浏览器自动化方案 ✅
4. 增加检查节点：健康检查、状态验证 ✅

## 阶段 1：基础设施重构 ✅

### 1.1 创建基础模块
- [x] `base.py` - BaseClient 基类（认证、请求、错误处理）
- [x] `constants.py` - API 端点、分类常量

### 1.2 重构认证模块
- [x] 移除 `auth.py` 中的 Playwright 登录
- [x] 保留 Cookie 认证
- [x] 增加 `browser_cookie3` 从 Chrome 获取 Cookie
- [x] 增加 dedao-dl 配置同步功能

## 阶段 2：内容模块拆分 ✅

### 2.1 课程模块
- [x] 创建 `course/` 目录
- [x] `course/client.py` - 课程 API 客户端
- [x] `course/downloader.py` - 课程下载器

### 2.2 电子书模块
- [x] 创建 `ebook/` 目录
- [x] `ebook/client.py` - 电子书 API 客户端
- [x] `ebook/downloader.py` - 电子书下载器（使用 dedao-dl）

### 2.3 有声书模块
- [x] 创建 `audiobook/` 目录
- [x] 保留原有代码，通过 `__init__.py` 导出

## 阶段 3：集成 dedao-dl ✅

### 3.1 dedao-dl 封装
- [x] `dedao_dl.py` - dedao-dl 工具的 Python 封装
- [x] 实现配置同步（cookie 格式转换）
- [x] 实现下载接口封装

### 3.2 替换下载逻辑
- [x] 电子书下载 → 使用 dedao-dl
- [x] 课程下载 → 保持现有逻辑

## 阶段 4：检查节点 ✅

### 4.1 健康检查
- [x] `check_auth()` - 检查认证状态
- [x] `check_dl_tool()` - 检查 dedao-dl 工具状态
- [x] `sync_cookies()` - 同步 Chrome cookies

### 4.2 下载前验证
- [x] `check_prerequisites()` - 下载器前提条件检查

## 阶段 5：清理

- [x] 删除 playwright 相关代码
- [ ] 删除冗余代码（旧 ebook.py, client.py）
- [ ] 更新 CLI 入口
- [ ] 更新测试

## 新模块结构

```
src/dedao/
├── __init__.py          # 主入口
├── base.py              # 基础客户端 ✅
├── constants.py         # 常量定义 ✅
├── auth.py              # 认证（无 Playwright）✅
├── dedao_dl.py          # dedao-dl 封装 ✅
├── models.py            # 数据模型
├── cache.py             # 缓存
├── account.py           # 账户管理
│
├── course/
│   ├── __init__.py
│   ├── client.py        # 课程 API ✅
│   └── downloader.py    # 课程下载 ✅
│
├── ebook/
│   ├── __init__.py
│   ├── client.py        # 电子书 API ✅
│   └── downloader.py    # 电子书下载（dedao-dl）✅
│
├── audiobook/
│   └── __init__.py      # 有声书（向后兼容）
│
└── _audiobook_legacy.py # 有声书旧代码
```

## 使用示例

```python
from src.dedao import EbookDownloader, check_dl_tool

# 检查工具状态
status = check_dl_tool()
print(f"dedao-dl: {status['installed']}, logged in: {status['logged_in']}")

# 下载电子书
downloader = EbookDownloader(output_dir=Path('./downloads'))
result = downloader.download('ebook_id', output_format='md')

if result.success:
    print(f"下载完成: {result.output_files}")
```
