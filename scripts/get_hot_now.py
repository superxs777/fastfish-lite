#!/usr/bin/env python
"""
实时提取热点脚本。

支持从 API 拉取或从数据库读取。
- 默认：从 api.pearktrue.cn 拉取（12 平台约 15-30 秒）
- --from-db：从 hot_items_raw 读取（需先执行 fetch_hot_items.py），秒级完成，适合 OpenClaw Cron

示例：
  python scripts/get_hot_now.py --source 知乎
  python scripts/get_hot_now.py --category emotion --from-db   # 从 DB 读，避免超时
  python scripts/get_hot_now.py --category emotion --format json
  python scripts/get_hot_now.py --source 知乎 --save
"""

import argparse
import json
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

from core.daily_hot import (
    fetch_from_pearktrue,
    fetch_platforms,
    filter_items,
    get_push_configs,
    get_today_raw_items,
    save_raw_items,
)
from core.daily_hot import _dedupe_by_link
import time


def _format_text(items: list[dict], category_name: str | None = None) -> str:
    """格式化为可读文本。"""
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"【{category_name}】实时热点 {date_str}" if category_name else f"实时热点 {date_str}"
    lines = [header, ""]
    for i, item in enumerate(items[:30], 1):
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        source = item.get("source", "")
        hot = item.get("hot", "")
        if title:
            lines.append(f"{i}. [{source}] {title}")
            if hot:
                lines.append(f"   热度: {hot}")
            if link:
                lines.append(f"   {link}")
            lines.append("")
    return "\n".join(lines).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="实时提取热点")
    parser.add_argument(
        "--source",
        type=str,
        help="平台名，逗号分隔，如：知乎,百度,今日头条",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="类别 code，如 emotion，从 hot_push_config 读取 sources 和关键词过滤",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="输出格式，默认 text",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="写入 hot_items_raw 表",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="每平台最多条数，默认 20",
    )
    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="列出 API 支持的所有平台（约 45 个），用于配置 sources",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="从 hot_items_raw 读取（需先执行 fetch_hot_items.py），避免 API 拉取超时",
    )
    args = parser.parse_args()

    if args.list_platforms:
        platforms = fetch_platforms()
        if platforms:
            print(f"共 {len(platforms)} 个平台：")
            for i, p in enumerate(platforms, 1):
                print(f"  {i}. {p}")
        else:
            print("获取平台列表失败")
        return 0 if platforms else 1

    if not args.source and not args.category:
        parser.error("请指定 --source、--category 或 --list-platforms")

    sources = []
    include_keywords = []
    exclude_keywords = []
    category_name = None

    if args.category:
        configs = get_push_configs()
        found = None
        for cfg in configs:
            if (cfg.get("category_code") or "").lower() == args.category.lower():
                found = cfg
                break
        if not found:
            try:
                from core.db import get_connection
                with get_connection() as conn:
                    cur = conn.execute(
                        """SELECT sources, include_keywords, exclude_keywords, category_name
                           FROM hot_push_config WHERE LOWER(category_code) = ? LIMIT 1""",
                        (args.category.lower(),),
                    )
                    row = cur.fetchone()
                if row:
                    found = {
                        "sources": json.loads(row[0]) if row[0] else [],
                        "include_keywords": json.loads(row[1]) if row[1] else [],
                        "exclude_keywords": json.loads(row[2]) if row[2] else [],
                        "category_name": row[3],
                    }
            except Exception:
                pass
        if not found:
            print(f"未找到类别 {args.category} 的配置")
            return 1
        sources = found.get("sources") or []
        include_keywords = found.get("include_keywords") or []
        exclude_keywords = found.get("exclude_keywords") or []
        category_name = found.get("category_name", args.category)

    if args.source:
        sources = [s.strip() for s in args.source.split(",") if s.strip()]
        if not sources:
            print("--source 为空")
            return 1
        if not category_name:
            category_name = ",".join(sources[:3])

    # sources 为空时：--from-db 可取全部平台；未指定 --from-db 时，--category 也尝试从 DB 读（init 默认 sources=[]）
    use_from_db = args.from_db
    if not sources and not use_from_db and args.category:
        use_from_db = True  # 隐式从 DB 读，避免「无有效平台」错误

    if not sources and not use_from_db:
        print("无有效平台（--from-db 时 sources 可为空，表示取全部；或指定 --source 平台列表）")
        return 1

    all_items = []
    if use_from_db:
        # 从数据库读取，秒级完成，适合 OpenClaw Cron 避免超时
        all_items = get_today_raw_items(sources)
        if not all_items:
            print("今日无数据，请先执行: python scripts/fetch_hot_items.py", file=sys.stderr)
            return 1
    else:
        # 实时从 API 拉取，需指定 sources
        fetched_at = int(time.time())
        for source in sources:
            items = fetch_from_pearktrue(source)
            for item in items[: args.limit]:
                item["source"] = source
                all_items.append(item)
            if args.save and items:
                save_raw_items(source, items[: args.limit], fetched_at)

    if include_keywords or exclude_keywords:
        all_items = filter_items(all_items, include_keywords, exclude_keywords)
    all_items = _dedupe_by_link(all_items)
    all_items.sort(key=lambda x: (x.get("source", ""), x.get("rank", 999)))

    if args.format == "json":
        out = json.dumps(all_items, ensure_ascii=False, indent=2)
        print(out)
    else:
        print(_format_text(all_items, category_name))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"执行异常: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
