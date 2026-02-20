"""
fastfish-lite FastAPI 应用入口。

开源精简版：无微信发布/授权，支持本地 HTML 预览。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pathlib import Path

from fastapi import Depends, File, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from api.auth import require_auth
from config import get_settings
from core.articles import get_available_list, get_article_by_id, ingest_article, ingest_articles_batch, update_article
from core.compliance import check_compliance_for_content
from core.render import get_available_styles, render_markdown_to_html, _SUPPORTED_STYLES
from core.template import normalize_to_wechat_format

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parent.parent

_STYLE_PREVIEW_MARKDOWN = """## 一缕春风过

三月将至，草长莺飞的时节已在眼前。这个春节离春天如此之近，让人忍不住期盼起来。

> 春天从不迟到，她只是悄悄地在枝头酝酿。待到新芽破土，便是满目生机。

我们可以期待：

- 冰雪消融，溪水潺潺
- 嫩绿初绽，花香盈袖
- 和风拂面，心旷神怡

**这份期盼**，让马年春节多了几分轻盈。仿佛钟声一响，就能听见春天在门外轻轻的脚步。

愿你我都能在春光里，遇见更好的自己。"""


class RenderBody(BaseModel):
    markdown: str
    format_style: str = "minimal"


class NormalizeBody(BaseModel):
    content: str


class CheckComplianceBody(BaseModel):
    title: str = ""
    content: str


class IngestArticleBody(BaseModel):
    title: str
    content: str
    cover_pic: str | None = None
    source_url: str | None = None
    task_id: int = 0
    category_id: int = 0
    author: str | None = None
    summary: str | None = None
    is_markdown: bool = False
    format_style: str = "minimal"
    auto_format: bool = True


class UpdateArticleBody(BaseModel):
    article_id: int
    title: str | None = None
    content: str | None = None
    cover_pic: str | None = None
    is_markdown: bool = False
    format_style: str | None = None


class IngestArticleItem(BaseModel):
    title: str
    content: str
    cover_pic: str | None = None
    source_url: str | None = None
    task_id: int = 0
    category_id: int = 0
    author: str | None = None
    summary: str | None = None
    is_markdown: bool = False
    format_style: str = "minimal"
    auto_format: bool = True


class IngestBatchBody(BaseModel):
    articles: list[IngestArticleItem]


app = FastAPI(
    title="fastfish-lite",
    description="开源精简版：公众号格式整理、敏感词检测、每日热点。微信发布需商业版。",
    version="0.1.0-lite",
)


@app.exception_handler(Exception)
def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("请求 %s %s 发生异常: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "fastfish-lite"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config/status")
def api_config_status(_: None = Depends(require_auth)) -> dict[str, Any]:
    """精简版配置状态：仅敏感词、API。"""
    from core.sensitive import get_checker
    settings = get_settings()
    checker = get_checker()
    local_loaded = checker._ensure_loaded()
    return {
        "api_host": settings.api_host,
        "api_port": settings.api_port,
        "api_base_url": str(settings.api_base_url),
        "sensitive": {
            "enabled": local_loaded,
            "local_lexicon": local_loaded,
            "hint": "已启用" if local_loaded else "未启用：请配置 data/sensitive_lexicon/Vocabulary/",
        },
        "originality": {"enabled": False, "hint": "原创度检测需商业版，请联系获取完整版 fastfish"},
    }


@app.get("/api/styles")
def api_styles(_: None = Depends(require_auth)) -> dict[str, Any]:
    styles = get_available_styles()
    base = get_settings().api_base_url
    for s in styles:
        s["preview_url"] = f"{base.rstrip('/')}/api/styles/preview/{s['id']}" if base else ""
    return {"styles": styles}


@app.get("/api/styles/preview/{style_id}", response_class=HTMLResponse)
def api_styles_preview(style_id: str) -> HTMLResponse:
    if style_id not in _SUPPORTED_STYLES:
        raise HTTPException(status_code=404, detail=f"样式不存在: {style_id}")
    html_body = render_markdown_to_html(_STYLE_PREVIEW_MARKDOWN, format_style=style_id)
    label = next((s["label"] for s in get_available_styles() if s["id"] == style_id), style_id)
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>样式预览 - {label}</title>
<style>body {{ max-width: 680px; margin: 0 auto; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}</style>
</head>
<body>
<div class="markdown-body">{html_body}</div>
<p style="color:#999;font-size:12px;">fastfish-lite 开源精简版 · 商业版请联系获取完整功能</p>
</body>
</html>"""
    return HTMLResponse(content=full_html)


@app.post("/api/articles/normalize")
def articles_normalize(body: NormalizeBody, _: None = Depends(require_auth)) -> dict[str, Any]:
    content, title = normalize_to_wechat_format(body.content)
    return {"ok": True, "content": content, "title": title or ""}


@app.post("/api/articles/check-compliance")
def articles_check_compliance(body: CheckComplianceBody, _: None = Depends(require_auth)) -> dict[str, Any]:
    return check_compliance_for_content(body.title, body.content)


@app.post("/api/images/upload")
def api_images_upload(file: UploadFile = File(...), _: None = Depends(require_auth)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/gif/webp 图片")
    try:
        content = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大，最大 10MB")
    ext = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    name = f"{uuid.uuid4().hex[:12]}{ext}"
    base = get_settings().images_base_path
    subdir = base / "uploaded"
    subdir.mkdir(parents=True, exist_ok=True)
    dest = subdir / name
    dest.write_bytes(content)
    return {"ok": True, "path": f"uploaded/{name}"}


@app.get("/api/articles/available")
def articles_available(_: None = Depends(require_auth)) -> dict[str, Any]:
    items = get_available_list()
    out = []
    for i, row in enumerate(items, start=1):
        out.append({
            "article_id": row["id"],
            "list_index": i,
            "title": row.get("rewritten_title") or "",
            "summary": row.get("summary") or "",
        })
    return {"items": out, "total": len(out)}


@app.get("/api/articles/preview-html/{article_id}", response_class=HTMLResponse)
def articles_preview_html(article_id: int, _: None = Depends(require_auth)) -> HTMLResponse:
    """本地 HTML 预览：生成完整 HTML 在浏览器中打开。"""
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"文章不存在: article_id={article_id}")
    title = article.get("rewritten_title") or "无标题"
    content = article.get("rewritten_content") or ""
    format_style = article.get("format_style") or "minimal"
    content_format = article.get("content_format") or "html"
    if content_format == "markdown":
        html_body = render_markdown_to_html(content, format_style=format_style)
    else:
        html_body = content
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>body {{ max-width: 680px; margin: 0 auto; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}</style>
</head>
<body>
<h1>{title}</h1>
<div class="markdown-body">{html_body}</div>
<p style="color:#999;font-size:12px;">fastfish-lite 本地预览 · 微信发布需商业版</p>
</body>
</html>"""
    return HTMLResponse(content=full_html)


@app.post("/api/articles/ingest")
def articles_ingest(body: IngestArticleBody, _: None = Depends(require_auth)) -> dict[str, Any]:
    return ingest_article(
        title=body.title,
        content=body.content,
        cover_pic=body.cover_pic,
        source_url=body.source_url,
        task_id=body.task_id,
        category_id=body.category_id,
        author=body.author,
        summary=body.summary,
        is_markdown=body.is_markdown,
        format_style=body.format_style,
        auto_format=body.auto_format,
    )


@app.post("/api/articles/ingest/markdown")
def articles_ingest_markdown(body: IngestArticleBody, _: None = Depends(require_auth)) -> dict[str, Any]:
    return ingest_article(
        title=body.title,
        content=body.content,
        cover_pic=body.cover_pic,
        source_url=body.source_url,
        task_id=body.task_id,
        category_id=body.category_id,
        author=body.author,
        summary=body.summary,
        is_markdown=True,
        format_style=body.format_style,
    )


@app.post("/api/articles/ingest/batch")
def articles_ingest_batch(body: IngestBatchBody, _: None = Depends(require_auth)) -> dict[str, Any]:
    items = [
        {
            "title": a.title,
            "content": a.content,
            "cover_pic": a.cover_pic,
            "source_url": a.source_url,
            "task_id": a.task_id,
            "category_id": a.category_id,
            "author": a.author,
            "summary": a.summary,
            "is_markdown": a.is_markdown,
            "format_style": a.format_style,
            "auto_format": a.auto_format,
        }
        for a in body.articles
    ]
    return ingest_articles_batch(items)


@app.post("/api/articles/update")
def articles_update(body: UpdateArticleBody, _: None = Depends(require_auth)) -> dict[str, Any]:
    return update_article(
        article_id=body.article_id,
        title=body.title,
        content=body.content,
        cover_pic=body.cover_pic,
        is_markdown=body.is_markdown,
        format_style=body.format_style,
    )


@app.post("/api/articles/render")
def articles_render(body: RenderBody, _: None = Depends(require_auth)) -> dict[str, Any]:
    html = render_markdown_to_html(body.markdown, body.format_style)
    return {"ok": True, "html": html, "format_style": body.format_style}
