"""
可发稿件访问层。

从 hot_article_rewritten 查询未分配稿件、按 id 读取单条；支持接入写入（OpenClaw 抓取结果写入）。
"""

from __future__ import annotations

import re
import time
from typing import Any

from core.db import get_connection

# 可发条件：未分配且标题非空
_AVAILABLE_SQL = """
SELECT id, rewritten_title, rewritten_pic, rewritten_content, create_time, format_style, content_format
FROM hot_article_rewritten
WHERE allocation_status = 0
  AND (rewritten_title IS NOT NULL AND TRIM(rewritten_title) != '')
ORDER BY create_time DESC
"""

_BY_ID_SQL = """
SELECT id, rewritten_title, rewritten_pic, rewritten_content, create_time, format_style, content_format
FROM hot_article_rewritten
WHERE id = ?
"""


def _strip_html(html: str | None, max_len: int = 100) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", "", html).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def get_available_list() -> list[dict[str, Any]]:
    with get_connection() as conn:
        conn.row_factory = _dict_row_factory
        rows = conn.execute(_AVAILABLE_SQL).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["summary"] = _strip_html(item.get("rewritten_content"))
        result.append(item)
    return result


def get_article_by_id(article_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.row_factory = _dict_row_factory
        row = conn.execute(_BY_ID_SQL, (article_id,)).fetchone()
    return row if row else None


def _dict_row_factory(cursor: Any, row: tuple) -> dict[str, Any]:
    names = [d[0] for d in cursor.description]
    return dict(zip(names, row))


def _normalize_literal_escapes(text: str) -> str:
    if not text or "\\" not in text:
        return text
    return text.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")


def _detect_content_format(content: str) -> str:
    if not content or not content.strip():
        return "markdown"
    c = content.strip()
    if re.search(r"<(p|div|h[1-6]|ul|ol|li|blockquote)\b", c, re.I):
        return "html"
    return "markdown"


def ingest_article(
    title: str,
    content: str,
    cover_pic: str | None = None,
    source_url: str | None = None,
    task_id: int = 0,
    category_id: int = 0,
    author: str | None = None,
    summary: str | None = None,
    is_markdown: bool = False,
    format_style: str = "minimal",
    auto_format: bool = False,
) -> dict[str, Any]:
    title = (title or "").strip()
    title = re.sub(r"\s*\([a-z0-9-]+\s+样式\)\s*$", "", title, flags=re.I)
    content = _normalize_literal_escapes((content or "").strip())
    if not title:
        return {"ok": False, "message": "标题不能为空", "article_id": None}
    ts = int(time.time())
    cover_pic = (cover_pic or "").strip() or None
    source_url = (source_url or "").strip() or None
    author = (author or "").strip() or None
    digest = (summary or "").strip() or None

    if auto_format:
        is_markdown = _detect_content_format(content) == "markdown"

    if not is_markdown and re.search(r"<(style|head)\b", content, re.I):
        return {
            "ok": False,
            "message": "检测到内容为完整 HTML（含 style/head）。请使用 --is-markdown 传入原始 Markdown，由系统在发布时渲染样式。禁止先 render-markdown 再 ingest HTML。",
            "article_id": None,
        }

    if is_markdown:
        content_to_store = content
        content_format = "markdown"
        from core.render import render_markdown_to_html
        content_html = render_markdown_to_html(content, format_style=format_style) if content else ""
    else:
        content_to_store = content
        content_format = "html"
        content_html = content

    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO hot_article
                   (task_id, category_id, source_title, source_pic, source_content, source_url,
                    rewritten_title, rewritten_pic, rewritten_content, allocation_status,
                    create_time, update_time)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (task_id, category_id, title, cover_pic, content_html, source_url, title, cover_pic, content_html, ts, ts),
            )
            orig_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO hot_article_rewritten
                   (original_article_id, task_id, category_id, rewritten_title, rewritten_pic, rewritten_content,
                    author, digest, allocation_status, format_style, content_format,
                    create_time, update_time, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                (orig_id, task_id, category_id, title, cover_pic, content_to_store, author, digest,
                 format_style, content_format, ts, ts, source_url),
            )
            rewritten_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"ok": True, "message": "已接入，已加入可发列表", "article_id": rewritten_id}
    except Exception as e:
        return {"ok": False, "message": str(e), "article_id": None}


def ingest_articles_batch(articles: list[dict[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for item in articles:
        r = ingest_article(
            title=item.get("title") or "",
            content=item.get("content") or "",
            cover_pic=item.get("cover_pic"),
            source_url=item.get("source_url"),
            task_id=int(item.get("task_id") or 0),
            category_id=int(item.get("category_id") or 0),
            author=item.get("author"),
            summary=item.get("summary"),
            is_markdown=bool(item.get("is_markdown", False)),
            format_style=str(item.get("format_style") or "minimal"),
            auto_format=bool(item.get("auto_format", False)),
        )
        results.append(r)
    success_count = sum(1 for r in results if r.get("ok"))
    return {
        "ok": success_count == len(articles) if articles else True,
        "total": len(articles),
        "success_count": success_count,
        "results": results,
    }


def update_article(
    article_id: int,
    title: str | None = None,
    content: str | None = None,
    cover_pic: str | None = None,
    is_markdown: bool = False,
    format_style: str | None = None,
) -> dict[str, Any]:
    article = get_article_by_id(article_id)
    if not article:
        return {"ok": False, "message": f"文章不存在: article_id={article_id}", "article_id": None}

    current_format_style = article.get("format_style") or "minimal"
    current_content_format = article.get("content_format") or "html"

    with get_connection() as conn:
        row = conn.execute(
            "SELECT published_count FROM hot_article_rewritten WHERE id = ?",
            (article_id,),
        ).fetchone()
        if row and row[0] and row[0] > 0:
            return {
                "ok": False,
                "message": f"文章已发布（published_count={row[0]}），不允许更新: article_id={article_id}",
                "article_id": None,
            }

    target_format_style = format_style if format_style is not None else current_format_style
    updates: list[str] = []
    values: list[Any] = []
    ts = int(time.time())
    content_format_to_set = current_content_format

    if title is not None:
        title = re.sub(r"\s*\([a-z0-9-]+\s+样式\)\s*$", "", title.strip(), flags=re.I)
        if not title:
            return {"ok": False, "message": "标题不能为空", "article_id": None}
        updates.append("rewritten_title = ?")
        values.append(title)

    if content is not None:
        content = _normalize_literal_escapes(content.strip())
        if not is_markdown and re.search(r"<(style|head)\b", content, re.I):
            return {
                "ok": False,
                "message": "检测到内容为完整 HTML（含 style/head）。请使用 --is-markdown 传入原始 Markdown。",
                "article_id": None,
            }
        if is_markdown:
            updates.append("rewritten_content = ?")
            values.append(content)
            updates.append("content_format = ?")
            values.append("markdown")
            content_format_to_set = "markdown"
        else:
            updates.append("rewritten_content = ?")
            values.append(content)
            updates.append("content_format = ?")
            values.append("html")
            content_format_to_set = "html"

    if format_style is not None:
        updates.append("format_style = ?")
        values.append(format_style)

    if cover_pic is not None:
        cover_pic = cover_pic.strip() or None
        if cover_pic:
            from core.utils import validate_cover_image_path
            from config import get_settings
            is_valid, error_msg = validate_cover_image_path(cover_pic, get_settings().images_base_path)
            if not is_valid:
                return {
                    "ok": False,
                    "message": f"封面图路径无效: {error_msg or '未知错误'}",
                    "article_id": None,
                }
        updates.append("rewritten_pic = ?")
        values.append(cover_pic)

    if not updates:
        return {"ok": False, "message": "没有提供要更新的字段", "article_id": None}

    updates.append("update_time = ?")
    values.append(ts)

    try:
        with get_connection() as conn:
            values.append(article_id)
            sql = f"UPDATE hot_article_rewritten SET {', '.join(updates)} WHERE id = ?"
            conn.execute(sql, values)

            article_updates: list[str] = []
            article_values: list[Any] = []
            if title is not None:
                article_updates.append("rewritten_title = ?")
                article_values.append(title)
            if content is not None:
                if content_format_to_set == "markdown" and content:
                    from core.render import render_markdown_to_html
                    content_html = render_markdown_to_html(content, format_style=target_format_style)
                else:
                    content_html = content
                article_updates.append("rewritten_content = ?")
                article_values.append(content_html)
            if cover_pic is not None:
                article_updates.append("rewritten_pic = ?")
                article_values.append(cover_pic)

            if article_updates:
                article_updates.append("update_time = ?")
                article_values.append(ts)
                orig_id_row = conn.execute(
                    "SELECT original_article_id FROM hot_article_rewritten WHERE id = ?",
                    (article_id,),
                ).fetchone()
                if orig_id_row:
                    orig_id = orig_id_row[0]
                    article_values.append(orig_id)
                    article_sql = f"UPDATE hot_article SET {', '.join(article_updates)} WHERE id = ?"
                    conn.execute(article_sql, article_values)

        return {"ok": True, "message": "文章已更新", "article_id": article_id}
    except Exception as e:
        return {"ok": False, "message": f"更新失败: {str(e)}", "article_id": None}


__all__ = [
    "get_available_list",
    "get_article_by_id",
    "ingest_article",
    "ingest_articles_batch",
    "update_article",
]
