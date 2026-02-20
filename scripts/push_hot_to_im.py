#!/usr/bin/env python
"""
每日热点推送脚本。

从 hot_items_raw 读取今日数据，按配置过滤后推送到飞书/钉钉/Telegram。
支持单次推送（如 08:00）或多次推送（如 08:00,10:00,...,20:00 每 2 小时）。

定时任务示例：
- 每 2 小时（8-20 点）：0 8,10,12,14,16,18,20 * * *
- 单次 8 点：0 8 * * *
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
    already_pushed_in_window,
    already_pushed_today,
    filter_items,
    format_push_message,
    get_push_configs,
    get_today_raw_items,
    push_to_im,
    record_push_history,
)
from core.daily_hot import _dedupe_by_link


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def main() -> int:
    log("=== 开始每日热点推送 ===")
    configs = get_push_configs()
    if not configs:
        log("未找到启用的推送配置，跳过")
        return 0

    import os
    force = os.getenv("HOT_PUSH_FORCE", "").strip().lower() in ("1", "true", "yes")
    now = time.localtime()
    current_time = f"{now.tm_hour:02d}:{now.tm_min:02d}"
    pushed = 0
    for cfg in configs:
        # 跳过 openclaw 占位配置（由 OpenClaw Cron + announce 推送）
        if (cfg.get("im_channel") or "").lower() == "openclaw" or (
            cfg.get("webhook_url") or ""
        ).strip().startswith("openclaw://"):
            log(f"  [{cfg.get('category_name')}] openclaw 模式，跳过（由 OpenClaw Cron 推送）")
            continue

        push_time = (cfg.get("push_time") or "").strip()
        push_times = [t.strip() for t in push_time.split(",") if t.strip()]
        if not force and push_times and current_time not in push_times:
            continue

        config_id = cfg["id"]
        # 多时间点用 2 小时窗口去重，单时间点用今日去重
        if len(push_times) > 1:
            if already_pushed_in_window(config_id, 2):
                log(f"  [{cfg['category_name']}] 本窗口已推送，跳过")
                continue
        else:
            if already_pushed_today(config_id):
                log(f"  [{cfg['category_name']}] 今日已推送，跳过")
                continue

        sources = cfg.get("sources") or []
        # sources 为空表示取全部平台，推送时仅按关键词过滤
        items = get_today_raw_items(sources)
        items = filter_items(
            items,
            cfg.get("include_keywords") or [],
            cfg.get("exclude_keywords") or [],
        )
        items = _dedupe_by_link(items)
        items.sort(key=lambda x: (x.get("source", ""), x.get("rank", 999)))
        items = items[: cfg.get("max_items", 10)]

        if not items:
            log(f"  [{cfg['category_name']}] 过滤后无数据，跳过推送")
            continue

        content = format_push_message(items, cfg["category_name"])
        ok, err = push_to_im(
            cfg.get("im_channel", "feishu"),
            cfg.get("webhook_url", ""),
            content,
        )
        item_ids = [x["id"] for x in items if x.get("id")]

        if ok:
            record_push_history(config_id, item_ids, 1)
            log(f"  [{cfg['category_name']}] 推送成功，{len(items)} 条")
            pushed += 1
        else:
            record_push_history(config_id, item_ids, 0, err)
            log(f"  [{cfg['category_name']}] 推送失败: {err}")

    log(f"=== 推送完成，成功 {pushed} 个配置 ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
