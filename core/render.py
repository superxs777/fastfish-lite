"""
改写与排版：Markdown 转 HTML + 注入预设 CSS（Inline）。

提供 3 套预设样式（商务、极简、文艺），通过 format_style 参数切换。
重点优化 H2 标题、引用块（Blockquote）、图片圆角。

支持两种 CSS Inline 方式：
1. 使用 premailer 库（推荐，更完善）
2. 简化版自写逻辑（备选，不依赖额外库）
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import markdown

# 尝试导入 premailer，如果未安装则使用简化版
try:
    from premailer import Premailer
    PREMAILER_AVAILABLE = True
except ImportError:
    PREMAILER_AVAILABLE = False

logger = logging.getLogger(__name__)

# 预设样式名称
_STYLE_BUSINESS = "business"
_STYLE_MINIMAL = "minimal"
_STYLE_LITERARY = "literary"
_DEFAULT_STYLE = _STYLE_MINIMAL

# phycat 主题列表（亮色系 + 暗色系）
_PHYCAT_LIGHT_STYLES = [
    "phycat-cherry",      # 樱桃红
    "phycat-caramel",     # 焦糖橙
    "phycat-forest",      # 森绿
    "phycat-mint",        # 薄荷青
    "phycat-sky",         # 天蓝
    "phycat-prussian",    # 普鲁士蓝
    "phycat-sakura",      # 樱花粉
    "phycat-mauve",       # 淡紫
]
_PHYCAT_DARK_STYLES = [
    "phycat-vampire",     # 吸血鬼
    "phycat-radiation",   # 辐射
    "phycat-abyss",       # 深渊
]

# 新增 Typora 衍生样式（中文名）
_EXTRA_STYLES = [
    "orange-heart",   # 橙心
    "lapis",          # 青玉
    "rainbow",        # 彩虹
]

# 支持的样式列表
_SUPPORTED_STYLES = (
    [_STYLE_BUSINESS, _STYLE_MINIMAL, _STYLE_LITERARY] +
    _PHYCAT_LIGHT_STYLES +
    _PHYCAT_DARK_STYLES +
    _EXTRA_STYLES
)

# 样式显示名称（供 IM 等前端展示）
_STYLE_LABELS: dict[str, str] = {
    "business": "商务",
    "minimal": "极简",
    "literary": "文艺",
    "phycat-cherry": "樱桃红",
    "phycat-caramel": "焦糖橙",
    "phycat-forest": "森绿",
    "phycat-mint": "薄荷青",
    "phycat-sky": "天蓝",
    "phycat-prussian": "普鲁士蓝",
    "phycat-sakura": "樱花粉",
    "phycat-mauve": "淡紫",
    "phycat-vampire": "吸血鬼",
    "phycat-radiation": "辐射",
    "phycat-abyss": "深渊",
    "orange-heart": "橙心",
    "lapis": "青玉",
    "rainbow": "彩虹",
}


def get_available_styles() -> list[dict[str, Any]]:
    """返回可用样式列表，供 IM 等前端展示选择。

    每项含 index（序号）、id、label，便于按序号展示和用户回复数字选择。

    Returns:
        [{"index": 1, "id": "minimal", "label": "极简"}, ...]
    """
    return [
        {"index": i, "id": s, "label": _STYLE_LABELS.get(s, s)}
        for i, s in enumerate(_SUPPORTED_STYLES, start=1)
    ]


def _get_styles_dir() -> Path:
    """返回预设 CSS 文件所在目录。"""
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "assets" / "styles"


def _load_css(style_name: str) -> str:
    """加载指定样式的 CSS 文件内容。
    
    支持两种路径：
    1. 基础样式：直接位于 styles_dir（如 business.css）
    2. phycat 主题：位于 styles_dir/phycat/（如 phycat-cherry.css）
    """
    styles_dir = _get_styles_dir()
    
    # 检查是否是 phycat 主题
    if style_name.startswith("phycat-"):
        css_file = styles_dir / "phycat" / f"{style_name}.css"
    else:
        css_file = styles_dir / f"{style_name}.css"
    
    if not css_file.is_file():
        logger.warning(f"样式文件不存在: {css_file}")
        return ""
    
    try:
        css_content = css_file.read_text(encoding="utf-8")
        # 解析 :root 中的 CSS 变量并替换，因 premailer/WeChat 不支持 var()
        css_content = _resolve_css_variables(css_content)
        return css_content
    except Exception as e:
        logger.exception(f"读取样式文件失败: {css_file}, 错误: {e}")
        return ""


def _resolve_css_variables(css: str) -> str:
    """解析 :root 中的 CSS 变量，将 var(--name) 替换为实际值。

    premailer 和微信等环境不支持 CSS 变量，需在 inline 前预解析。
    """
    if not css or ":root" not in css:
        return css
    # 解析 :root { --var: value; ... }
    root_match = re.search(r":root\s*\{([^}]+)\}", css, re.DOTALL)
    if not root_match:
        return css
    vars_map: dict[str, str] = {}
    for decl in root_match.group(1).split(";"):
        decl = decl.strip()
        if ":" in decl:
            key, _, val = decl.partition(":")
            key = key.strip()
            val = val.strip().rstrip(";").strip()
            if key.startswith("--"):
                vars_map[key] = val
    if not vars_map:
        return css
    # 替换 var(--name) 为实际值
    result = css
    for var_name, var_val in vars_map.items():
        result = re.sub(rf"var\(\s*{re.escape(var_name)}\s*\)", var_val, result)
    # 移除 :root 块（变量已解析，避免 premailer 处理异常）
    result = re.sub(r":root\s*\{[^}]*\}\s*", "", result)
    return result


def _inline_css_premailer(html: str, css: str) -> str:
    """使用 premailer 库将 CSS 内联到 HTML（推荐方式）。

    Args:
        html: HTML 内容
        css: CSS 样式文本

    Returns:
        内联 CSS 后的 HTML
    """
    if not PREMAILER_AVAILABLE:
        logger.warning("premailer 未安装，回退到简化版 CSS Inline")
        return _inline_css_simple(html, css)

    if not css or not html:
        return html

    try:
        # 将 CSS 包装在 <style> 标签中
        html_with_style = f"<style>{css}</style>{html}"
        # 使用 premailer 转换
        p = Premailer(
            html_with_style,
            strip_important=False,
            keep_style_tags=False,
            disable_validation=True,
        )
        result = p.transform()
        # 移除添加的 <style> 标签（premailer 会将其内联）
        return result
    except Exception as e:
        logger.warning(f"premailer 处理失败，回退到简化版: {e}")
        return _inline_css_simple(html, css)


def _inline_css_simple(html: str, css: str) -> str:
    """将 CSS 规则内联到 HTML 元素（简化版：仅处理常见选择器）。

    这是一个基础实现，用于处理简单的 CSS 规则。
    对于复杂场景，建议使用 premailer。

    Args:
        html: HTML 内容
        css: CSS 样式文本

    Returns:
        内联 CSS 后的 HTML
    """
    if not css or not html:
        return html

    css_rules: list[tuple[str, str]] = []
    pattern = r"([^{]+)\{([^}]+)\}"
    for match in re.finditer(pattern, css):
        selector = match.group(1).strip()
        declarations = match.group(2).strip()
        if selector and declarations:
            css_rules.append((selector, declarations))

    result = html
    for selector, declarations in css_rules:
        selector_clean = selector.strip()
        # 支持常见的选择器：标签选择器
        if selector_clean in ["h1", "h2", "h3", "blockquote", "img", "p", "ul", "ol", "li"]:
            # 匹配标签，处理已有 style 属性的情况
            tag_pattern = f"<{selector_clean}([^>]*?)>"
            def replace_tag(m: re.Match) -> str:
                attrs = m.group(1)
                existing_style_match = re.search(r'style=["\']([^"\']*)["\']', attrs, re.IGNORECASE)
                if existing_style_match:
                    existing_style = existing_style_match.group(1)
                    new_attrs = re.sub(
                        r'style=["\'][^"\']*["\']',
                        f'style="{existing_style}; {declarations}"',
                        attrs,
                        flags=re.IGNORECASE
                    )
                else:
                    new_attrs = f'{attrs} style="{declarations}"'
                return f"<{selector_clean}{new_attrs}>"
            result = re.sub(tag_pattern, replace_tag, result, flags=re.IGNORECASE)

    return result


def _inline_css(html: str, css: str, use_premailer: bool = True) -> str:
    """将 CSS 规则内联到 HTML 元素。

    Args:
        html: HTML 内容
        css: CSS 样式文本
        use_premailer: 是否优先使用 premailer（默认 True）

    Returns:
        内联 CSS 后的 HTML
    """
    if use_premailer and PREMAILER_AVAILABLE:
        return _inline_css_premailer(html, css)
    else:
        return _inline_css_simple(html, css)


def _normalize_markdown_newlines(text: str) -> str:
    """规范 Markdown 换行，确保 IM 粘贴的文本中 引用(>) 列表(-) 分隔线(---) 能被正确解析。"""
    if not text or not text.strip():
        return text
    t = text
    # 句末紧跟 > 时补换行，使 blockquote 生效
    t = re.sub(r"([。！？])\s*>", r"\1\n\n>", t)
    # "xxx: - 项目" 或 "xxx: -项目" 补换行，使列表生效
    t = re.sub(r"([：:])\s*-\s*", r"\1\n\n- ", t)
    # "xxx。---  yyy" 补换行，使 --- 渲染为分隔线而非字面量
    t = re.sub(r"([。！？\s])\s*---\s+", r"\1\n\n---\n\n", t)
    return t


def render_markdown_to_html(
    markdown_text: str,
    format_style: str = _DEFAULT_STYLE,
    use_premailer: bool = True,
) -> str:
    """将 Markdown 文本渲染为 HTML，并注入预设 CSS（Inline）。

    Args:
        markdown_text: Markdown 格式的文本
        format_style: 样式名称，可选 'business'、'minimal'、'literary'，默认 'minimal'
        use_premailer: 是否使用 premailer 进行 CSS Inline（默认 True，如果未安装会自动回退）

    Returns:
        渲染后的 HTML（含内联样式）
    """
    if not markdown_text or not str(markdown_text).strip():
        return ""

    markdown_text = _normalize_markdown_newlines(markdown_text)

    if format_style not in _SUPPORTED_STYLES:
        logger.warning(f"不支持的样式 '{format_style}'，使用默认样式 '{_DEFAULT_STYLE}'")
        format_style = _DEFAULT_STYLE

    md = markdown.Markdown(extensions=["extra", "codehilite", "tables"])
    html = md.convert(markdown_text)

    css = _load_css(format_style)
    if css:
        html = _inline_css(html, css, use_premailer=use_premailer)
        logger.debug(f"已应用样式 '{format_style}'，使用 premailer={use_premailer and PREMAILER_AVAILABLE}")
    else:
        logger.warning(f"样式文件 '{format_style}.css' 不存在，跳过 CSS Inline")

    return html


def render_markdown_to_html_simple(
    markdown_text: str,
    format_style: str = _DEFAULT_STYLE,
) -> str:
    """简化版：仅 Markdown 转 HTML，不注入 CSS（用于测试或外部 CSS）。"""
    if not markdown_text or not str(markdown_text).strip():
        return ""
    md = markdown.Markdown(extensions=["extra", "codehilite", "tables"])
    return md.convert(markdown_text)


__all__ = [
    "render_markdown_to_html",
    "render_markdown_to_html_simple",
    "get_available_styles",
    "_SUPPORTED_STYLES",
]
