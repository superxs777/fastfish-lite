#!/usr/bin/env python
"""
每日热点拉取脚本。

从 api.pearktrue.cn 拉取全部平台（约 45 个）热点，写入 hot_items_raw 表。
每次拉取前清空旧数据，推送时按配置的关键词过滤。

定时任务示例（北京 7:00、14:00、18:00）：
- Linux: TZ=Asia/Shanghai 下 0 7,14,18 * * *
"""

import sys
import time
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
    delete_all_raw_items,
    fetch_from_pearktrue,
    fetch_platforms,
    save_raw_items,
)


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def main() -> int:
    log("=== 开始拉取每日热点 ===")
    platforms = fetch_platforms()
    if not platforms:
        log("获取平台列表失败，跳过拉取")
        return 0

    # 每次拉取前清空全部旧数据
    deleted = delete_all_raw_items()
    if deleted:
        log(f"  清空旧数据 {deleted} 条")

    fetched_at = int(time.time())
    total = 0
    for source in sorted(platforms):
        items = fetch_from_pearktrue(source)
        if items:
            n = save_raw_items(source, items, fetched_at)
            total += n
            log(f"  {source}: 写入 {n} 条")
        else:
            log(f"  {source}: 无数据或拉取失败")

    log(f"=== 拉取完成，共 {total} 条（{len(platforms)} 个平台）===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
