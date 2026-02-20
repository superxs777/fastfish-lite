"""
fastfish-lite 数据库初始化与连接管理。

使用 schema_lite.sql，不含微信、激活相关表。
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config import get_settings


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _get_schema_path() -> Path:
    return _get_project_root() / "sql" / "schema_lite.sql"


def _database_has_schema(conn: sqlite3.Connection) -> bool:
    """判断是否已存在主表。"""
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='hot_article_rewritten' LIMIT 1"
    )
    return cur.fetchone() is not None


def init_database() -> None:
    """初始化 SQLite 数据库。"""
    settings = get_settings()
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = _get_schema_path()
    if not schema_path.exists():
        raise FileNotFoundError(f"schema 文件不存在: {schema_path}")

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        if not _database_has_schema(conn):
            with schema_path.open("r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()
        _seed_if_empty(conn)
        _migrate_rewritten_columns(conn)
        _migrate_format_style_columns(conn)
        _migrate_hot_push_tables(conn)


def _migrate_rewritten_columns(conn: sqlite3.Connection) -> None:
    """补充 author、digest 列。"""
    info = conn.execute("PRAGMA table_info(hot_article_rewritten)").fetchall()
    names = [row[1] for row in info]
    if "author" not in names:
        conn.execute("ALTER TABLE hot_article_rewritten ADD COLUMN author TEXT")
    if "digest" not in names:
        conn.execute("ALTER TABLE hot_article_rewritten ADD COLUMN digest TEXT")


def _migrate_format_style_columns(conn: sqlite3.Connection) -> None:
    """补充 format_style、content_format 列。"""
    info = conn.execute("PRAGMA table_info(hot_article_rewritten)").fetchall()
    names = [row[1] for row in info]
    if "format_style" not in names:
        conn.execute("ALTER TABLE hot_article_rewritten ADD COLUMN format_style TEXT DEFAULT 'minimal'")
    if "content_format" not in names:
        conn.execute("ALTER TABLE hot_article_rewritten ADD COLUMN content_format TEXT DEFAULT 'html'")
        conn.execute("UPDATE hot_article_rewritten SET content_format = 'html' WHERE content_format IS NULL")


def _migrate_hot_push_tables(conn: sqlite3.Connection) -> None:
    """补充每日热点推送相关表。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS hot_items_raw (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL,
            title           TEXT,
            link            TEXT,
            desc_text       TEXT,
            hot             TEXT,
            rank            INTEGER DEFAULT 0,
            fetched_at      INTEGER NOT NULL,
            create_time     INTEGER
        )"""
    )
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hot_items_raw_source_fetched "
            "ON hot_items_raw(source, fetched_at)"
        )
    except sqlite3.OperationalError:
        pass
    conn.execute(
        """CREATE TABLE IF NOT EXISTS hot_push_config (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            category_code       TEXT NOT NULL,
            category_name       TEXT NOT NULL,
            sources             TEXT NOT NULL,
            include_keywords    TEXT,
            exclude_keywords    TEXT,
            push_time           TEXT NOT NULL,
            im_channel          TEXT NOT NULL,
            webhook_url         TEXT NOT NULL,
            max_items           INTEGER DEFAULT 10,
            is_active           INTEGER DEFAULT 1,
            create_time         INTEGER,
            update_time         INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS hot_push_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id       INTEGER NOT NULL,
            pushed_at       INTEGER NOT NULL,
            items_count     INTEGER DEFAULT 0,
            item_ids        TEXT,
            status          INTEGER NOT NULL DEFAULT 0,
            error_msg       TEXT,
            create_time     INTEGER,
            FOREIGN KEY (config_id) REFERENCES hot_push_config(id)
        )"""
    )
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hot_push_history_config_pushed "
            "ON hot_push_history(config_id, pushed_at)"
        )
    except sqlite3.OperationalError:
        pass


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    """若表为空则插入种子数据。"""
    ts = int(time.time())
    cur = conn.execute("SELECT COUNT(*) FROM media_platform")
    if cur.fetchone()[0] == 0:
        conn.execute(
            """INSERT INTO media_platform (id, name, code, status, create_time, update_time)
               VALUES (1, '微信公众号', 'wechat_mp', 1, ?, ?)""",
            (ts, ts),
        )
    cur = conn.execute("SELECT COUNT(*) FROM local_user")
    if cur.fetchone()[0] == 0:
        conn.execute(
            """INSERT INTO local_user (id, username, status, create_time, update_time)
               VALUES (1, 'default', 'normal', ?, ?)""",
            (ts, ts),
        )


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """获取 SQLite 连接的上下文管理器。"""
    settings = get_settings()
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()


__all__ = ["init_database", "get_connection"]
