#!/usr/bin/env python
"""
从 data/hot_push_keywords.json 读取关键词，更新 hot_push_config 中所有配置。
用于修改关键词后同步到数据库，无需改代码。
"""

import json
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


def main() -> int:
    cfg_path = _project_root / "data" / "hot_push_keywords.json"
    if not cfg_path.exists():
        print(f"错误: 未找到 {cfg_path}")
        print("请创建该文件，格式示例：")
        print('  {"include_keywords": ["情感","恋爱",...], "exclude_keywords": ["政治","时政","军事"]}')
        return 1

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"错误: 读取配置失败: {e}")
        return 1

    include = data.get("include_keywords")
    exclude = data.get("exclude_keywords")
    include_kw = list(include) if isinstance(include, list) else []
    exclude_kw = list(exclude) if isinstance(exclude, list) else []

    with get_connection() as conn:
        cur = conn.execute("SELECT id, category_name FROM hot_push_config")
        rows = cur.fetchall()

    if not rows:
        print("hot_push_config 无数据，请先执行 init_hot_push_config.py")
        return 1

    for row in rows:
        cfg_id, name = row[0], row[1]
        with get_connection() as conn:
            conn.execute(
                "UPDATE hot_push_config SET include_keywords = ?, exclude_keywords = ?, update_time = ? WHERE id = ?",
                (json.dumps(include_kw, ensure_ascii=False), json.dumps(exclude_kw, ensure_ascii=False), int(time.time()), cfg_id),
            )
        print(f"已更新 config id={cfg_id} [{name}]")

    print(f"已从 {cfg_path} 同步关键词到 {len(rows)} 个配置")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
