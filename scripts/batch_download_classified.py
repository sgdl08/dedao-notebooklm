#!/usr/bin/env python3
"""批量下载得到电子书并按主题分类存放"""

import sys
import os
import time
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(__file__))

from dedao.ebook import EbookClient
from dedao.models import EbookDetail
from utils.config import get_config

# ==================== 分类规则 ====================

CATEGORY_RULES: Dict[str, List[str]] = {
    "投资_金融_经济": [
        "投资", "基金", "股票", "债券", "估值", "资产配置", "理财", "财富",
        "金融", "银行", "保险", "期货", "期权", "ETF", "REITs", "指数",
        "经济", "货币", "周期", "资本", "财务", "博弈论",
        "芒格", "巴菲特", "格雷厄姆", "博格", "林奇", "达利欧", "马克斯",
        "塔勒布", "斯皮茨纳格尔", "霍华德", "邱国鹭", "李录",
        "持续买入", "超额收益", "攒钱", "养老",
        "一如既往", "豪泽尔", "利率史",
        "股市天才", "股市真规则", "漫步华尔街",
        "趋势交易", "趋势永存", "动量",
        "钱：7步", "罗宾斯",
        "资产托管", "崛起的",
        "陈志武", "第一财经",
    ],
    "管理_商业_战略": [
        "管理", "战略", "组织", "领导", "团队", "华为", "敏捷", "项目",
        "商业", "商业模式", "创业", "产品", "运营", "营销", "交付",
        "咨询", "顾问", "麦肯锡", "黄奇帆", "宁高宁",
        "B端", "数字化", "转型",
        "冯唐成事", "斯隆自传", "通用汽车",
        "漫画丰田生产方式", "丰田",
        "极简项目管理", "项目管理式",
        "远见：如何规划职业",
        "与运气竞争", "克里斯坦森",
        "发现利润区",
        "认识顾客",
        "华章教材",
        "领导梯队", "查兰",
        "成就", "施密特",
        "管理的常识", "陈春花",
    ],
    "科技_AI_数字化": [
        "AI", "人工智能", "ChatGPT", "DeepSeek", "AIGC", "芯片", "半导体",
        "区块链", "Web3", "RWA", "科技", "技术", "数据", "云计算",
        "数字", "智能", "互联网", "分布式", "Spark", "DevOps", "Jenkins",
        "领域驱动", "DDD", "重构", "编程", "Python", "算法",
        "凯文·凯利", "库兹韦尔",
        "浪潮将至", "浪潮之巅", "加来道雄",
        "未来呼啸而来", "未来架构", "云原生",
        "混合云架构", "阿里云运维",
        "函数响应式", "程序员修炼",
        "Spring Cloud", "极简Spring",
        "第二大脑", "涂子沛", "数商", "数据之巅", "数文明",
        "打造第二大脑", "蒂亚戈",
        "从一到无穷大", "量子力学",
        "为什么：关于因果关系", "朱迪亚·珀尔",
        "自私的基因", "道金斯",
        "格拉德威尔",
        "女士品茶", "统计学",
        "牛津科普",
    ],
    "思维_认知_心理学": [
        "思维", "认知", "思考", "决策", "逻辑", "批判性", "心理", "行为",
        "行为经济", "概率", "模型", "理性", "非理性", "直觉", "聪明人",
        "费曼", "丹尼特", "侯世达", "万维钢", "刘擎", "采铜", "芒格之道",
        "纳瓦尔", "原则", "反常识", "反脆弱", "肥尾",
        "专注的真相", "专注", "系统之美", "系统思维",
        "格局", "态度", "掌控",
        "被讨厌的勇气", "幸福", "象与骑象人",
        "精要主义", "清单革命", "如何形成清晰的观点",
        "以大制胜", "亚当斯",
        "我们赖以生存的故事", "麦克亚当斯",
        "人间值得", "中村恒子",
        "裸猿", "莫利斯",
        "第二座山", "布鲁克斯",
        "清醒地活", "辛格",
        "拥抱可能", "埃格尔",
        "自驱型成长", "大脑修复",
        "想点大事", "刘晗",
        "系统", "梅多斯",
    ],
    "健康_运动_医学": [
        "健康", "运动", "健身", "医学", "医", "饮食", "断食", "减脂",
        "力量训练", "跑步", "呼吸", "衰老", "长寿", "疾病",
        "拒绝生病", "阿古斯",
        "免疫系统", "死掉",
        "明年更年轻",
        "逆龄饮食", "养生",
        "女生呵护指南", "六层楼",
        "命悬一线", "ICU", "薄世宁",
    ],
    "人文_历史_社会": [
        "历史", "文明", "文化", "社会", "政治", "外交", "大国", "帝国",
        "全球", "世界", "战争", "丝绸之路", "季风", "东南亚", "通史",
        "毛泽东", "马伯庸", "余秋雨", "老舍",
        "西方史纲", "李筠",
        "指挥与控制", "核武器",
        "大而不倒", "索尔金",
        "大学的精神", "文学回忆录", "木心",
        "中华帝国的衰落", "魏斐德",
        "告别百年激进", "温铁军",
        "道德情操论", "亚当·斯密",
        "君主论", "马基雅维里",
        "中国治理评论",
        "我本芬芳", "杨本芬",
        "中国为什么有前途", "翟东升",
        "大国", "大棋局", "布热津斯基",
        "故乡的味道", "风雅宋", "吴钩",
        "全球通史", "斯塔夫里",
        "四世同堂", "中华",
        "贼巢", "斯图尔特",
        "美国增长的起落", "戈登",
        "中国家庭资产管理", "财富传承",
        "小地方", "故乡",
    ],
    "个人成长_沟通": [
        "成长", "精进", "自律", "习惯", "沟通", "表达", "演讲", "写作",
        "阅读", "学习", "记忆", "笔记", "自信", "内向", "亲密关系",
        "品格", "品格力量",
        "重新找回自己", "自我实现", "自我决定", "30岁人生",
        "关于说话的一切", "内容公式", "不抱怨的规则",
        "不凌乱", "整理信息", "奥野宣之",
        "带人要同频", "管人要共情",
        "每天最重要", "游戏改变人生",
        "您厉害您赚得多", "找事", "就业",
        "高分读书法", "研究的方法", "价值心法",
        "新媒体信息编辑", "准备", "教育",
        "创意", "核心竞争力",
    ]
}

CATEGORY_FALLBACK = "其他"


def classify_book(title: str, author: str) -> str:
    """根据书名和作者分类"""
    text = f"{title} {author}"
    # 优先级：命中关键词最多的分类
    scores: Dict[str, int] = {}
    for cat, keywords in CATEGORY_RULES.items():
        score = sum(1 for kw in keywords if kw.lower() in text.lower())
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return CATEGORY_FALLBACK


def classify_all_books(books: List[EbookDetail]) -> Dict[str, List[EbookDetail]]:
    """将所有书按分类归组"""
    categories: Dict[str, List[EbookDetail]] = {}
    for book in books:
        extra = book.extra if isinstance(book.extra, dict) else {}
        cat = classify_book(book.title, book.author)
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(book)
    return categories


# ==================== 下载逻辑 ====================

@dataclass
class BatchResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    failed_books: List[Tuple[str, str]] = field(default_factory=list)  # (title, error)
    skipped_books: List[str] = field(default_factory=list)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def download_all_ebooks(
    base_dir: str,
    batch_size: int = 5,
    delay_seconds: float = 3.0,
    dry_run: bool = False,
    skip_existing: bool = True,
    verbose: bool = False,
) -> BatchResult:
    """批量下载所有电子书"""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    config = get_config()
    if not config.dedao_cookie:
        print("错误：Cookie 未配置，请先运行 dedao-nb login")
        sys.exit(1)

    # 延迟导入避免循环依赖
    from dedao.ebook import EbookDownloader

    client = EbookClient(cookie=config.dedao_cookie)
    downloader = EbookDownloader(output_dir=Path(base_dir))

    # 1. 获取所有电子书
    print("正在获取电子书列表...")
    all_books = []
    page = 1
    while True:
        books = client.get_ebook_list(page=page, page_size=50)
        if not books:
            break
        all_books.extend(books)
        if len(books) < 50:
            break
        page += 1

    print(f"共找到 {len(all_books)} 本电子书")

    # 2. 分类
    categories = classify_all_books(all_books)
    print(f"\n分类结果：")
    for cat, books in sorted(categories.items()):
        print(f"  {cat}: {len(books)} 本")

    # 3. 保存分类索引
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    index_path = Path(base_dir) / "分类索引.md"
    index_lines = ["# 得到电子书分类索引\n", f"总计 {len(all_books)} 本\n"]
    for cat, books in sorted(categories.items()):
        index_lines.append(f"\n## {cat} ({len(books)}本)\n")
        for b in books:
            extra = b.extra if isinstance(b.extra, dict) else {}
            book_id = extra.get("id", "?")
            index_lines.append(f"- [{b.title}](../{cat}/{b.title}.md) — {b.author} (ID:{book_id})")
    index_path.write_text("\n".join(index_lines), encoding="utf-8")
    print(f"\n分类索引已保存: {index_path}")

    if dry_run:
        print("\n[dry-run] 不执行实际下载")
        return BatchResult(total=len(all_books))

    # 4. 批量下载
    result = BatchResult(total=len(all_books))
    print(f"\n开始批量下载（每批 {batch_size} 本，间隔 {delay_seconds}s）...\n")

    # 按分类顺序下载，同分类内按ID倒序（新书优先）
    download_queue = []
    for cat, books in sorted(categories.items()):
        for b in books:
            extra = b.extra if isinstance(b.extra, dict) else {}
            enid = extra.get("enid", "")
            book_id = str(extra.get("id", ""))
            # 优先用 enid（对所有书有效），回退到数字 ID
            identifier = enid if enid else book_id
            download_queue.append((cat, b, identifier))

    for i, (cat, book, book_id) in enumerate(download_queue):
        # 创建分类目录
        cat_dir = Path(base_dir) / cat
        cat_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已存在
        md_file = cat_dir / f"{book.title}.md"
        if skip_existing and md_file.exists() and md_file.stat().st_size > 0:
            logger.info(f"[{i+1}/{len(download_queue)}] 跳过(已存在): {book.title}")
            result.skipped += 1
            result.skipped_books.append(book.title)
            continue

        # 下载到分类目录
        downloader.output_dir = cat_dir
        try:
            logger.info(f"[{i+1}/{len(download_queue)}] 下载: {book.title}")
            dl_result = downloader.download(book_id, output_format="md")
            if dl_result.success:
                result.success += 1
                logger.info(f"  ✓ 成功")
            else:
                result.failed += 1
                result.failed_books.append((book.title, dl_result.error or "未知错误"))
                logger.warning(f"  ✗ 失败: {dl_result.error}")
        except Exception as e:
            result.failed += 1
            result.failed_books.append((book.title, str(e)))
            logger.error(f"  ✗ 异常: {e}")

        # 批次间延时
        if (i + 1) % batch_size == 0 and i < len(download_queue) - 1:
            logger.info(f"--- 批次完成，等待 {delay_seconds}s ---")
            time.sleep(delay_seconds)

    # 5. 汇总
    print(f"\n{'='*50}")
    print(f"下载完成！")
    print(f"  总计: {result.total}")
    print(f"  成功: {result.success}")
    print(f"  跳过: {result.skipped}")
    print(f"  失败: {result.failed}")
    if result.failed_books:
        print(f"\n失败列表：")
        for title, err in result.failed_books:
            print(f"  - {title}: {err[:80]}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="批量下载得到电子书并分类")
    parser.add_argument("-o", "--output", default="/Users/fei/Documents/dedao-ebooks", help="输出目录")
    parser.add_argument("-b", "--batch", type=int, default=5, help="每批下载数量")
    parser.add_argument("-d", "--delay", type=float, default=3.0, help="批次间隔秒数")
    parser.add_argument("--dry-run", action="store_true", help="仅分类不下载")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已存在文件")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")
    args = parser.parse_args()

    download_all_ebooks(
        base_dir=args.output,
        batch_size=args.batch,
        delay_seconds=args.delay,
        dry_run=args.dry_run,
        skip_existing=not args.no_skip,
        verbose=args.verbose,
    )
