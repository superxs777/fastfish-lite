#!/usr/bin/env python3
"""
fastfish-lite CLI 工具。

供 OpenClaw Skills 通过 system.run 调用，封装 fastfish-lite HTTP API。
微信发布、授权等需商业版。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import webbrowser
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings

_COMMERCIAL_HINT = "微信发布、授权、多账号管理需商业版，请联系获取完整版 fastfish"


def get_api_base_url() -> str:
    settings = get_settings()
    base = (os.getenv("MEDIA_AGENT_BASE_URL") or os.getenv("FASTFISH_BASE_URL") or "").strip()
    if base:
        return base.rstrip("/")
    host = settings.api_host
    if host == "0.0.0.0":
        host = "127.0.0.1"
    return f"http://{host}:{settings.api_port}"


def get_auth_headers() -> dict[str, str]:
    headers = {}
    api_key = os.getenv("MEDIA_AGENT_API_KEY") or get_settings().api_key
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def call_api(method: str, endpoint: str, data: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    base_url = get_api_base_url()
    url = f"{base_url}{endpoint}"
    headers = {"Content-Type": "application/json", **get_auth_headers()}
    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=headers, timeout=timeout)
        elif method.upper() == "POST":
            r = requests.post(url, headers=headers, json=data or {}, timeout=timeout)
        else:
            return {"ok": False, "error": f"不支持的 HTTP 方法: {method}"}
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"API 调用失败: {str(e)}"}


def _upload_image(path: str) -> str | None:
    p = Path(path.strip())
    if not p.is_file() or not p.exists():
        return None
    try:
        with open(p, "rb") as f:
            files = {"file": (p.name or "image.jpg", f, "image/jpeg")}
            base = get_api_base_url()
            headers = get_auth_headers()
            r = requests.post(f"{base}/api/images/upload", headers=headers, files=files, timeout=60)
            r.raise_for_status()
            data = r.json()
            if data.get("ok") and data.get("path"):
                return data["path"]
    except Exception:
        pass
    return None


def _upload_local_images_in_content(content: str) -> str:
    base = get_settings().images_base_path
    def replace_md(m):
        src = m.group(2)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        path = Path(src)
        if not path.is_absolute():
            path = base / src
        if path.exists() and path.is_file():
            uploaded = _upload_image(str(path))
            if uploaded:
                return f"![{m.group(1)}]({uploaded})"
        return m.group(0)
    content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_md, content)
    return content


def cmd_get_available_articles(args: argparse.Namespace) -> dict[str, Any]:
    return call_api("GET", "/api/articles/available")


def cmd_ingest_article(args: argparse.Namespace) -> dict[str, Any]:
    content_file = getattr(args, "content_file", None)
    content_stdin = getattr(args, "content_stdin", False)
    content = getattr(args, "content", None)
    if content_stdin:
        content = sys.stdin.read()
    elif content_file:
        with open(content_file, "r", encoding="utf-8") as f:
            content = f.read()
    if content is None:
        return {"ok": False, "error": "需要提供 --content、--content-file 或 --content-stdin"}
    content = _upload_local_images_in_content(content)
    cover_pic = getattr(args, "cover_pic", None)
    if cover_pic and not cover_pic.startswith(("http://", "https://")):
        uploaded = _upload_image(cover_pic)
        if uploaded:
            cover_pic = uploaded
    title = getattr(args, "title", None)
    if not title:
        return {"ok": False, "error": "需要提供 --title"}
    data = {
        "title": title,
        "content": content,
        "cover_pic": cover_pic,
        "source_url": getattr(args, "source_url", None),
        "task_id": getattr(args, "task_id", None) or 0,
        "category_id": getattr(args, "category_id", None) or 0,
        "author": getattr(args, "author", None),
        "summary": getattr(args, "summary", None),
        "is_markdown": getattr(args, "is_markdown", False),
        "format_style": getattr(args, "format_style", None) or "minimal",
        "auto_format": not getattr(args, "no_auto_format", False),
    }
    data = {k: v for k, v in data.items() if v is not None}
    return call_api("POST", "/api/articles/ingest", data)


def cmd_update_article(args: argparse.Namespace) -> dict[str, Any]:
    content = getattr(args, "content", None)
    content_file = getattr(args, "content_file", None)
    if getattr(args, "content_stdin", False):
        content = sys.stdin.read()
    elif content_file:
        with open(content_file, "r", encoding="utf-8") as f:
            content = f.read()
    if content is not None:
        content = _upload_local_images_in_content(content)
    cover_pic = getattr(args, "cover_pic", None)
    if cover_pic and not cover_pic.startswith(("http://", "https://")):
        uploaded = _upload_image(cover_pic)
        if uploaded:
            cover_pic = uploaded
    article_id = getattr(args, "article_id", None)
    if article_id is None:
        return {"ok": False, "error": "需要提供 --article-id"}
    data = {
        "article_id": article_id,
        "title": getattr(args, "title", None),
        "content": content,
        "cover_pic": cover_pic,
        "is_markdown": getattr(args, "is_markdown", False),
        "format_style": getattr(args, "format_style", None),
    }
    data = {k: v for k, v in data.items() if v is not None}
    return call_api("POST", "/api/articles/update", data)


def cmd_ingest_articles_batch(args: argparse.Namespace) -> dict[str, Any]:
    articles_file = getattr(args, "articles_file", None)
    if not articles_file:
        return {"ok": False, "error": "需要提供 --articles-file"}
    with open(articles_file, "r", encoding="utf-8") as f:
        articles = json.load(f)
    return call_api("POST", "/api/articles/ingest/batch", {"articles": articles})


def cmd_publish_article(args: argparse.Namespace) -> dict[str, Any]:
    return {"ok": False, "message": _COMMERCIAL_HINT}


def cmd_preview_article(args: argparse.Namespace) -> dict[str, Any]:
    """Lite 版：本地 HTML 预览，在浏览器中打开。"""
    list_index = getattr(args, "list_index", None)
    article_id = getattr(args, "article_id", None)
    if list_index is not None:
        items = call_api("GET", "/api/articles/available")
        if not items.get("ok") or not items.get("items"):
            return {"ok": False, "error": "无法获取可发列表"}
        idx = min(list_index - 1, len(items["items"]) - 1)
        if idx < 0:
            return {"ok": False, "error": f"list_index {list_index} 无效"}
        article_id = items["items"][idx].get("article_id")
    if article_id is None:
        return {"ok": False, "error": "需要提供 --article-id 或 --list-index"}
    return cmd_preview_html(argparse.Namespace(article_id=article_id))


def cmd_preview_html(args: argparse.Namespace) -> dict[str, Any]:
    """生成 HTML 并在默认浏览器中打开。"""
    article_id = getattr(args, "article_id", None)
    if article_id is None:
        return {"ok": False, "error": "需要提供 --article-id"}
    base = get_api_base_url()
    url = f"{base}/api/articles/preview-html/{article_id}"
    headers = get_auth_headers()
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        html = r.text
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"获取预览失败: {str(e)}"}
    import tempfile
    tmp = Path(tempfile.gettempdir()) / f"fastfish_preview_{article_id}.html"
    tmp.write_text(html, encoding="utf-8")
    webbrowser.open(f"file://{tmp}")
    return {"ok": True, "preview_path": str(tmp), "message": "已在浏览器中打开本地预览"}


def cmd_render_markdown(args: argparse.Namespace) -> dict[str, Any]:
    markdown = getattr(args, "markdown", None)
    if not markdown:
        return {"ok": False, "error": "需要提供 --markdown"}
    return call_api("POST", "/api/articles/render", {
        "markdown": markdown,
        "format_style": getattr(args, "format_style", None) or "minimal",
    })


def cmd_normalize_content(args: argparse.Namespace) -> dict[str, Any]:
    content = getattr(args, "content", None)
    content_file = getattr(args, "content_file", None)
    if getattr(args, "content_stdin", False):
        content = sys.stdin.read()
    elif content_file:
        with open(content_file, "r", encoding="utf-8") as f:
            content = f.read()
    if not content:
        return {"ok": False, "error": "需要提供 --content、--content-file 或 --content-stdin"}
    return call_api("POST", "/api/articles/normalize", {"content": content})


def cmd_check_compliance(args: argparse.Namespace) -> dict[str, Any]:
    title = getattr(args, "title", None) or ""
    content = getattr(args, "content", None)
    content_file = getattr(args, "content_file", None)
    if getattr(args, "content_stdin", False):
        content = sys.stdin.read()
    elif content_file:
        with open(content_file, "r", encoding="utf-8") as f:
            content = f.read()
    if not content:
        return {"ok": False, "error": "需要提供 --content、--content-file 或 --content-stdin"}
    return call_api("POST", "/api/articles/check-compliance", {"title": title, "content": content})


def cmd_check_publish_status(args: argparse.Namespace) -> dict[str, Any]:
    return call_api("GET", "/api/config/status")


def cmd_get_available_styles(args: argparse.Namespace) -> dict[str, Any]:
    return call_api("GET", "/api/styles")


def cmd_need_commercial(cmd_name: str) -> dict[str, Any]:
    return {"ok": False, "message": f"{cmd_name} 需商业版。{_COMMERCIAL_HINT}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="fastfish-lite CLI - 公众号格式整理、敏感词检测、每日热点")
    parser.add_argument("--json", help="JSON 格式参数")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("get-available-articles", help="获取可发稿件列表")
    sub.add_parser("get-available-styles", help="获取可用样式列表")
    sub.add_parser("check-publish-status", help="检查发布前检测状态")

    ingest_p = sub.add_parser("ingest-article", help="接入单条文章")
    ingest_p.add_argument("--title", required=True)
    ingest_p.add_argument("--content")
    ingest_p.add_argument("--content-file")
    ingest_p.add_argument("--content-stdin", action="store_true")
    ingest_p.add_argument("--cover-pic")
    ingest_p.add_argument("--source-url")
    ingest_p.add_argument("--task-id", type=int)
    ingest_p.add_argument("--category-id", type=int)
    ingest_p.add_argument("--author")
    ingest_p.add_argument("--summary")
    ingest_p.add_argument("--is-markdown", action="store_true")
    ingest_p.add_argument("--no-auto-format", action="store_true")
    ingest_p.add_argument("--format-style", default="minimal")

    batch_p = sub.add_parser("ingest-articles-batch", help="批量接入")
    batch_p.add_argument("--articles-file", required=True)

    update_p = sub.add_parser("update-article", help="更新文章")
    update_p.add_argument("--article-id", type=int, required=True)
    update_p.add_argument("--title")
    update_p.add_argument("--content")
    update_p.add_argument("--content-file")
    update_p.add_argument("--content-stdin", action="store_true")
    update_p.add_argument("--cover-pic")
    update_p.add_argument("--is-markdown", action="store_true")
    update_p.add_argument("--format-style")

    pub_p = sub.add_parser("publish-article", help="发布（Lite 返回需商业版）")
    pub_p.add_argument("--article-id", type=int)
    pub_p.add_argument("--list-index", type=int)
    prev_p = sub.add_parser("preview-article", help="预览（Lite 为本地 HTML 预览）")
    prev_p.add_argument("--article-id", type=int)
    prev_p.add_argument("--list-index", type=int)
    prev_html = sub.add_parser("preview-html", help="本地 HTML 预览并打开浏览器")
    prev_html.add_argument("--article-id", type=int, required=True)

    render_p = sub.add_parser("render-markdown", help="渲染 Markdown")
    render_p.add_argument("--markdown", required=True)
    render_p.add_argument("--format-style", default="minimal")

    norm_p = sub.add_parser("normalize-content", help="公众号格式整理")
    norm_p.add_argument("--content")
    norm_p.add_argument("--content-file")
    norm_p.add_argument("--content-stdin", action="store_true")

    check_p = sub.add_parser("check-compliance", help="敏感词检测")
    check_p.add_argument("--title")
    check_p.add_argument("--content")
    check_p.add_argument("--content-file")
    check_p.add_argument("--content-stdin", action="store_true")

    args = parser.parse_args()

    if args.json:
        try:
            j = json.loads(args.json)
            args = argparse.Namespace(**j)
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handlers = {
        "get-available-articles": cmd_get_available_articles,
        "get-available-styles": cmd_get_available_styles,
        "check-publish-status": cmd_check_publish_status,
        "ingest-article": cmd_ingest_article,
        "ingest-articles-batch": cmd_ingest_articles_batch,
        "update-article": cmd_update_article,
        "publish-article": cmd_publish_article,
        "preview-article": cmd_preview_article,
        "preview-html": cmd_preview_html,
        "render-markdown": cmd_render_markdown,
        "normalize-content": cmd_normalize_content,
        "check-compliance": cmd_check_compliance,
    }

    handler = handlers.get(args.command)
    if handler:
        result = handler(args)
    else:
        result = {"ok": False, "error": f"未知命令: {args.command}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
