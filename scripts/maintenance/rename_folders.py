#!/usr/bin/env python3
"""Rename course folders in the configured download directory."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from utils import get_config, load_config

NAME_MAPPING = {
    "5閸掑棝鎸撻崯鍡梊ue11f闂勨挋宄扮唨绾偓": "5分钟商学院·基础",
    "瀵姵绲块梿\ue7ca铚傞嚋娴滅儤濮囩挧鍕甛ue1f3": "张潇雨·个人投资课",
    "娴ｆ洖鍨拌矾鐠愩垻绮℃径褑\ue1f3閿涘牆鍕炬惔锔芥）閺囪揪绱?": "何帆·财经大课（年度日历）",
    "娑揬ue15e娴楁禍褌绗熼弽鐓庣湰璺弶搴濊荡閻氭粍鍏?": "中国产业格局·李丰猜想",
    "婵″倷缍嶅鈧崣鎴漒ue122鐎涙劗娈戦懟杈玕ue1e2濞兼粌濮?": "如何开发孩子的英语潜力",
    "鐎逛礁鎮滄稉婊呮畱缁狅紕鎮婄€涳箒\ue1f3": "宁向东的管理学课",
    "鐠佲晛鍙忕€瑰爼鐝拹銊╁櫤鏉╁洤銇囬獮瀵告畱閻儴鐦戦弬瑙刓ue50d": "让全家高质量过大年的知识方案",
    "閸怽ue21e娲╄矾妤傛\ue505閸樺灏扮€涳箒\ue1f3": "冯雪·高血压医学课",
    "閸怽ue21e娲╄矾妤傛\ue505閼村倸灏扮€涳箒\ue1f3": "冯雪·高血脂医学课",
    "閹孩鐗遍幋鎰礋濠曟棁\ue189妤傛ɑ澧?": "怎样成为演讲高手",
    "閺堝鏅ョ拋\ue160绮屾担鐘垫畱閻梻鈹掗懗钘夊": "有效训练你的研究能力",
    "閺夊海鐟ч弶銉傜兘鈧艾绶氱拹銏犵槣閼穃ue046鏁辨稊瀣熅": "李笑来·通往财富自由之路",
    "閼村彉绗夐懞鐢攱鈧孩鐗遍幋鎰礋妤傛ɑ鏅ョ€涳缚绡勯惃鍕眽": "脱不花·怎样成为高效学习的人",
    "闂勫牊鎹ｇ拹銇㈢柉鍤滈幋鎴濆絺鐏炴洖绺鹃悶鍡梊ue11f": "陈海贤·自我发展心理学",
    "闂刓ue046鍩楀В宥堢箖娑揬ue044銈介獮瀵告畱閸忋劌\ue69c閺傝": "陪父母过一个好年的全套方案",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量重命名课程目录")
    parser.add_argument("--target-dir", default="", help="目标目录；默认使用配置中的 download_dir")
    return parser.parse_args()


def main() -> int:
    load_config()
    args = parse_args()
    target_dir = Path(args.target_dir) if args.target_dir else Path(get_config().download_dir)
    target_dir = target_dir.expanduser().resolve()

    if not target_dir.exists():
        print(f"错误：目录不存在 - {target_dir}")
        return 1

    success_count = 0
    skip_count = 0
    error_count = 0

    for old_name, new_name in NAME_MAPPING.items():
        old_path = target_dir / old_name
        new_path = target_dir / new_name

        if not old_path.exists():
            if new_path.exists():
                skip_count += 1
            else:
                error_count += 1
                print(f"[未找到] {old_name!r}")
            continue

        try:
            old_path.rename(new_path)
            print(f"[成功] -> {new_name}")
            success_count += 1
        except Exception as exc:
            print(f"[失败] {old_name!r}: {exc}")
            error_count += 1

    print(f"完成。成功: {success_count}，跳过: {skip_count}，失败: {error_count}")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
