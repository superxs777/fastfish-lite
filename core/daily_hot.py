"""
每日热点推送模块。

数据源：api.pearktrue.cn（公益免费）
支持平台映射 + 关键词过滤，推送到飞书/钉钉/Telegram。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests

from core.db import get_connection

logger = logging.getLogger(__name__)

_HOT_API_BASE = os.getenv("HOT_API_BASE", "https://api.pearktrue.cn").rstrip("/")
_REQUEST_TIMEOUT = 15


def fetch_platforms() -> list[str]:
    """从 api.pearktrue.cn 获取支持的平台列表（约 45 个）。

    Returns:
        平台名列表，如 ['微博', '知乎', '百度贴吧', ...]
    """
    url = f"{_HOT_API_BASE}/api/dailyhot/"
    try:
        r = requests.get(url, timeout=_REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("拉取平台列表失败: %s", e)
        return []
    except json.JSONDecodeError as e:
        logger.warning("解析平台列表 JSON 失败: %s", e)
        return []

    if data.get("code") not in (200, 0):
        return []

    data_obj = data.get("data")
    if isinstance(data_obj, dict) and "platforms" in data_obj:
        platforms = data_obj.get("platforms")
        return list(platforms) if isinstance(platforms, list) else []
    return []


def fetch_from_pearktrue(source: str) -> list[dict[str, Any]]:
    """从 api.pearktrue.cn 拉取指定平台的热点数据。

    Args:
        source: 平台名，如「微博热搜」「知乎」

    Returns:
        热点列表，每项含 title、link、desc、hot、rank 等
    """
    url = f"{_HOT_API_BASE}/api/dailyhot/"
    try:
        r = requests.get(url, params={"title": source}, timeout=_REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("拉取热点失败 source=%s: %s", source, e)
        return []
    except json.JSONDecodeError as e:
        logger.warning("解析热点 JSON 失败 source=%s: %s", source, e)
        return []

    code = data.get("code")
    if code not in (200, 0):
        logger.warning("热点 API 返回异常 source=%s code=%s: %s", source, code, data.get("message", ""))
        return []

    items = data.get("data")
    if not isinstance(items, list):
        return []

    result = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or ""
        link = item.get("mobileUrl") or item.get("url") or item.get("link") or ""
        desc = item.get("desc") or ""
        hot = str(item.get("hot", "")) if item.get("hot") is not None else ""
        if title:
            result.append({
                "title": title,
                "link": link,
                "desc": desc,
                "hot": hot,
                "rank": i + 1,
            })
    return result


def delete_raw_items_before(cutoff_ts: int) -> int:
    """删除 fetched_at 早于 cutoff_ts 的 raw 数据，用于定期清理历史。

    Returns:
        删除条数
    """
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM hot_items_raw WHERE fetched_at < ?", (cutoff_ts,))
        return cur.rowcount


def delete_all_raw_items() -> int:
    """清空 hot_items_raw 表全部数据（每次拉取前调用）。

    Returns:
        删除条数
    """
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM hot_items_raw")
        return cur.rowcount


def save_raw_items(source: str, items: list[dict], fetched_at: int) -> int:
    """将拉取的热点写入 hot_items_raw 表。

    Returns:
        写入条数
    """
    ts = int(time.time())
    count = 0
    with get_connection() as conn:
        for item in items:
            conn.execute(
                """INSERT INTO hot_items_raw
                   (source, title, link, desc_text, hot, rank, fetched_at, create_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source,
                    item.get("title", ""),
                    item.get("link", ""),
                    item.get("desc", ""),
                    item.get("hot", ""),
                    item.get("rank", 0),
                    fetched_at,
                    ts,
                ),
            )
            count += 1
    return count


def get_push_configs() -> list[dict[str, Any]]:
    """获取所有启用的推送配置。"""
    with get_connection() as conn:
        cur = conn.execute(
            """SELECT id, category_code, category_name, sources, include_keywords,
                      exclude_keywords, push_time, im_channel, webhook_url, max_items
               FROM hot_push_config WHERE is_active = 1"""
        )
        rows = cur.fetchall()
    configs = []
    for row in rows:
        configs.append({
            "id": row[0],
            "category_code": row[1],
            "category_name": row[2],
            "sources": json.loads(row[3]) if row[3] else [],
            "include_keywords": json.loads(row[4]) if row[4] else [],
            "exclude_keywords": json.loads(row[5]) if row[5] else [],
            "push_time": row[6],
            "im_channel": row[7],
            "webhook_url": row[8],
            "max_items": row[9] or 10,
        })
    return configs


def _match_keywords(text: str, keywords: list[str]) -> bool:
    """检查文本是否包含任一关键词（不区分大小写）。"""
    if not keywords:
        return False
    lower = (text or "").lower()
    for kw in keywords:
        if kw and kw.lower() in lower:
            return True
    return False


def filter_items(
    items: list[dict],
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> list[dict]:
    """按关键词过滤热点。

    规则：先排除含 exclude 的，再按 include 筛选（若 include 非空）。
    """
    filtered = []
    for item in items:
        title = item.get("title", "") or ""
        desc = item.get("desc", "") or ""
        text = f"{title} {desc}"

        if exclude_keywords and _match_keywords(text, exclude_keywords):
            continue
        if include_keywords and not _match_keywords(text, include_keywords):
            continue
        filtered.append(item)
    return filtered


def get_today_raw_items(sources: list[str]) -> list[dict]:
    """获取今日拉取的 raw 数据。sources 为空时取全部平台，否则按 source 过滤。"""
    ts = int(time.time())
    today_start = ts - (ts % 86400) - 8 * 3600  # 当日 0 点（东八区近似）
    today_end = today_start + 86400

    if sources:
        placeholders = ",".join("?" * len(sources))
        source_clause = f"source IN ({placeholders})"
        params = list(sources) + [today_start, today_end]
    else:
        source_clause = "1=1"
        params = [today_start, today_end]

    with get_connection() as conn:
        cur = conn.execute(
            f"""SELECT id, source, title, link, desc_text, hot, rank
                FROM hot_items_raw
                WHERE {source_clause}
                  AND fetched_at >= ? AND fetched_at < ?
                ORDER BY source, rank""",
            params,
        )
        rows = cur.fetchall()

    items = []
    for row in rows:
        items.append({
            "id": row[0],
            "source": row[1],
            "title": row[2],
            "link": row[3],
            "desc": row[4] or "",
            "hot": row[5] or "",
            "rank": row[6] or 0,
        })
    return items


def _dedupe_by_link(items: list[dict]) -> list[dict]:
    """按 link 去重，保留 rank 最小的。"""
    seen = {}
    for item in items:
        link = (item.get("link") or "").strip()
        if not link:
            continue
        if link not in seen or (item.get("rank", 999) < seen[link].get("rank", 999)):
            seen[link] = item
    return list(seen.values())


def format_push_message(items: list[dict], category_name: str) -> str:
    """格式化推送消息文本。"""
    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"【{category_name}】今日热点 {date_str}", ""]
    for i, item in enumerate(items[:20], 1):  # 最多 20 条
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        source = item.get("source", "")
        if title:
            lines.append(f"{i}. [{source}] {title}")
            if link:
                lines.append(f"   {link}")
            lines.append("")
    return "\n".join(lines).strip()


def push_to_feishu(webhook_url: str, content: str) -> tuple[bool, str]:
    """推送到飞书 Webhook。

    Returns:
        (成功与否, 错误信息)
    """
    if not webhook_url or not webhook_url.strip():
        return False, "webhook_url 为空"
    try:
        r = requests.post(
            webhook_url.strip(),
            json={"msg_type": "text", "content": {"text": content}},
            timeout=10,
        )
        resp = r.json()
        if resp.get("code") != 0 and resp.get("StatusCode") != 0:
            return False, resp.get("msg", resp.get("message", str(resp)))
        return True, ""
    except requests.RequestException as e:
        return False, str(e)
    except json.JSONDecodeError:
        return False, "响应非 JSON"


def push_to_dingtalk(webhook_url: str, content: str) -> tuple[bool, str]:
    """推送到钉钉 Webhook。

    Returns:
        (成功与否, 错误信息)
    """
    if not webhook_url or not webhook_url.strip():
        return False, "webhook_url 为空"
    try:
        r = requests.post(
            webhook_url.strip(),
            json={"msgtype": "text", "text": {"content": content}},
            timeout=10,
        )
        resp = r.json()
        if resp.get("errcode") != 0:
            return False, resp.get("errmsg", str(resp))
        return True, ""
    except requests.RequestException as e:
        return False, str(e)
    except json.JSONDecodeError:
        return False, "响应非 JSON"


def push_to_telegram(bot_token: str, chat_id: str, content: str) -> tuple[bool, str]:
    """推送到 Telegram Bot API。

    webhook_url 存 chat_id，bot_token 从环境变量 HOT_PUSH_TELEGRAM_BOT_TOKEN 读取。

    Returns:
        (成功与否, 错误信息)
    """
    if not bot_token or not bot_token.strip():
        return False, "HOT_PUSH_TELEGRAM_BOT_TOKEN 未配置"
    if not chat_id or not chat_id.strip():
        return False, "chat_id 为空"
    url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id.strip(), "text": content},
            timeout=10,
        )
        resp = r.json()
        if not resp.get("ok"):
            return False, resp.get("description", str(resp))
        return True, ""
    except requests.RequestException as e:
        return False, str(e)
    except json.JSONDecodeError:
        return False, "响应非 JSON"


def push_to_im(im_channel: str, webhook_url: str, content: str) -> tuple[bool, str]:
    """根据 im_channel 选择推送方式。telegram 时 webhook_url 存 chat_id。"""
    ch = (im_channel or "").lower()
    if ch == "feishu":
        return push_to_feishu(webhook_url, content)
    if ch == "dingtalk":
        return push_to_dingtalk(webhook_url, content)
    if ch == "telegram":
        import os
        token = os.getenv("HOT_PUSH_TELEGRAM_BOT_TOKEN", "").strip()
        return push_to_telegram(token, webhook_url, content)
    return False, f"不支持的 im_channel: {im_channel}"


def already_pushed_today(config_id: int) -> bool:
    """检查该 config 今日是否已推送。"""
    ts = int(time.time())
    today_start = ts - (ts % 86400) - 8 * 3600
    today_end = today_start + 86400
    with get_connection() as conn:
        cur = conn.execute(
            """SELECT 1 FROM hot_push_history
               WHERE config_id = ? AND pushed_at >= ? AND pushed_at < ? AND status = 1
               LIMIT 1""",
            (config_id, today_start, today_end),
        )
        return cur.fetchone() is not None


def already_pushed_in_window(config_id: int, window_hours: int = 2) -> bool:
    """检查该 config 在本 2 小时窗口内是否已推送（用于 8-20 每 2 小时推送）。"""
    now = time.localtime()
    y, m, d, hour = now.tm_year, now.tm_mon, now.tm_mday, now.tm_hour
    window_hour = (hour // window_hours) * window_hours
    window_start = int(time.mktime((y, m, d, window_hour, 0, 0, 0, 0, 0)))
    window_end = window_start + window_hours * 3600
    with get_connection() as conn:
        cur = conn.execute(
            """SELECT 1 FROM hot_push_history
               WHERE config_id = ? AND pushed_at >= ? AND pushed_at < ? AND status = 1
               LIMIT 1""",
            (config_id, window_start, window_end),
        )
        return cur.fetchone() is not None


def record_push_history(
    config_id: int,
    item_ids: list[int],
    status: int,
    error_msg: str | None = None,
) -> None:
    """记录推送历史。"""
    ts = int(time.time())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO hot_push_history
               (config_id, pushed_at, items_count, item_ids, status, error_msg, create_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (config_id, ts, len(item_ids), json.dumps(item_ids), status, error_msg, ts),
        )
