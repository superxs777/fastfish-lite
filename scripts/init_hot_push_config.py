#!/usr/bin/env python
"""
初始化每日热点推送配置。

部署时执行一次，插入情感类默认配置。
从环境变量读取：HOT_PUSH_FEISHU_WEBHOOK、HOT_PUSH_DINGTALK_WEBHOOK，
或 HOT_PUSH_TELEGRAM_BOT_TOKEN + HOT_PUSH_TELEGRAM_CHAT_ID。
若均未配置，则使用 openclaw 占位（适用于仅用 OpenClaw Cron + announce 推送到 Telegram 等）。
"""

import json
import os
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

from core.db import get_connection


def _load_keywords_config() -> tuple[list[str], list[str]]:
    """从 data/hot_push_keywords.json 读取关键词配置。"""
    cfg_path = _project_root / "data" / "hot_push_keywords.json"
    if not cfg_path.exists():
        print(f"提示: 未找到 {cfg_path}，将使用空关键词。请创建该文件并配置 include_keywords、exclude_keywords")
        return [], []
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        include = data.get("include_keywords")
        exclude = data.get("exclude_keywords")
        return (
            list(include) if isinstance(include, list) else [],
            list(exclude) if isinstance(exclude, list) else [],
        )
    except (json.JSONDecodeError, OSError) as e:
        print(f"警告: 读取 {cfg_path} 失败: {e}，使用空关键词")
        return [], []


def main() -> int:
    feishu = os.getenv("HOT_PUSH_FEISHU_WEBHOOK", "").strip()
    dingtalk = os.getenv("HOT_PUSH_DINGTALK_WEBHOOK", "").strip()
    tg_token = os.getenv("HOT_PUSH_TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.getenv("HOT_PUSH_TELEGRAM_CHAT_ID", "").strip()

    if feishu:
        webhook, im_channel = feishu, "feishu"
    elif dingtalk:
        webhook, im_channel = dingtalk, "dingtalk"
    elif tg_token and tg_chat:
        webhook, im_channel = tg_chat, "telegram"
    else:
        # 仅用 OpenClaw Cron + announce 时，无需配置 Webhook/Telegram
        webhook, im_channel = "openclaw://cron", "openclaw"

    ts = int(time.time())
    # sources 为空表示拉取全部平台，推送时仅按关键词过滤
    sources = json.dumps([], ensure_ascii=False)
    include_kw, exclude_kw = _load_keywords_config()
    include = json.dumps(include_kw, ensure_ascii=False)
    exclude = json.dumps(exclude_kw, ensure_ascii=False)

    with get_connection() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM hot_push_config")
        if cur.fetchone()[0] > 0:
            print("hot_push_config 已有数据，跳过初始化")
            return 0

        conn.execute(
            """INSERT INTO hot_push_config
               (category_code, category_name, sources, include_keywords, exclude_keywords,
                push_time, im_channel, webhook_url, max_items, is_active, create_time, update_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "emotion",
                "情感类",
                sources,
                include,
                exclude,
                "07:10,14:10,18:10",
                im_channel,
                webhook,
                30,
                1,
                ts,
                ts,
            ),
        )
    if im_channel == "openclaw":
        fastfish_path = _project_root.resolve()
        print("已初始化情感类配置（OpenClaw Cron 模式）。请创建 OpenClaw Cron 任务：")
        print("")
        print("  openclaw cron add --name \"每日热点\" --cron \"10 7,14,18 * * *\" --tz \"Asia/Shanghai\" \\")
        print("    --session isolated \\")
        print(f"    --message \"cd {fastfish_path} && python scripts/get_hot_now.py --category emotion --from-db，将输出作为今日热点简报发送\" \\")
        print("    --channel telegram --to \"你的ChatID\"")
        print("")
        print("  说明：--from-db 从数据库读取。拉取由系统 crontab 7:00/14:00/18:00 执行 fetch_hot_items.py，不要创建 OpenClaw 拉取任务。")
        print("  立即测试：openclaw cron run <job-id> --force")
    else:
        print("已初始化情感类推送配置")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
