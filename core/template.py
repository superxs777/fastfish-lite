"""
公众号文字规范整理：将用户自由文本转换为规范 Markdown。

仅在用户明确说「请按公众号规范整理」时调用，其他时候不处理。
"""

from __future__ import annotations

import re
from core.render import _normalize_markdown_newlines


def normalize_to_wechat_format(text: str) -> tuple[str, str | None]:
    """将自由文本整理为公众号规范 Markdown。

    规则：
    - [标签] 格式解析为对应 Markdown；[主标题] 不输出到 content，单独返回供 ingest 用
    - 一、二、三、等章节标题 -> ###
    - 演示环境:xxx -> 引用块
    - 导语、摘要、前言 -> 引用块
    - 要点、原因、方案 + 1.2.3. 或 - -> 列表
    - 按句号分段
    - 应用 _normalize_markdown_newlines

    Returns:
        (content, title): content 为整理后的 Markdown；title 为 [主标题] 提取的标题（仅 [标签] 格式时有值，其他为 None）
    """
    if not text or not text.strip():
        return text, None
    t = text.strip()

    # 1. 若已是 [标签] 格式，解析为 Markdown（主标题不输出到 content）
    if re.search(r"^\[(主标题|作者|摘要|导语|段落标题|段落|引用|列表|分隔线|图片|结语|署名)\]", t, re.M):
        content, title = _parse_template_to_markdown(t)
        return content, title

    # 2. 自由文本：先做换行规范化
    t = _normalize_markdown_newlines(t)

    # 3. 无段落分隔时按句号分段
    if "\n\n" not in t and re.search(r"[。！？]\s*[^\s。！？]", t):
        t = re.sub(r"([。！？])\s*", r"\1\n\n", t)
        t = re.sub(r"\n\n+", "\n\n", t).strip()

    # 4. 段落中「演示环境:xxx」转为引用块
    t = re.sub(
        r"([。！？\s]*)(演示环境[：:][^\n]+?)(?=[。！？\n]|$)",
        r"\1\n\n> \2\n\n",
        t,
    )
    t = re.sub(r"\n\n+", "\n\n", t).strip()

    # 5. 「导语」「导语简介」「摘要」「前言」开头的段落转引用块（增强样式效果）
    t = re.sub(
        r"(?m)^((?:导语|导语简介|摘要|前言)[：:][^\n]+)",
        r"> \1",
        t,
    )

    # 6. 「要点」「原因」「方案」等 + 1.2.3. 或 - 转为列表
    t = _convert_list_patterns(t)

    # 7. 「一、」「二、」等章节标题加 ###（行首出现时）
    t = re.sub(
        r"(?m)^([一二三四五六七八九十]+、[^\n]*)",
        r"### \1",
        t,
    )

    # 8. 「1. xxx：」「2. xxx：」等编号小节转 ###（增强结构，便于样式生效）
    t = re.sub(
        r"(?m)^(\d+[\.．]\s*[^\n]+[：:])\s*",
        r"### \1\n\n",
        t,
    )

    # 9. 首段若较短且无 ##，可视为二级标题
    lines = t.split("\n")
    first = lines[0].strip() if lines else ""
    if first and not first.startswith("#") and not first.startswith(">") and len(first) <= 35:
        if "\n\n" in t or len(lines) > 1:
            rest = "\n\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            t = f"## {first}\n\n{rest}" if rest else f"## {first}"

    return t.strip(), None


def _convert_list_patterns(text: str) -> str:
    """将「要点：1. 2. 3.」「原因：- xxx」等转为 Markdown 列表。"""
    # 匹配「要点：」「原因：」「方案：」等 + 同一行或后续行的 1.2.3. 或 - 列表
    prefix = r"(?:要点|原因|方案|建议|步骤|总结)[：:]"
    # 行内：要点：1.xxx 2.xxx 3.xxx —— 将数字编号替换为 -
    text = re.sub(
        rf"({prefix})\s*([^\n]+)",
        lambda m: m.group(1) + "\n\n" + re.sub(r"\d+[\.．]\s*", "- ", m.group(2))
        if re.search(r"\d+[\.．]\s*", m.group(2))
        else m.group(0),
        text,
    )
    # 多行：要点：\n1. xxx\n2. xxx —— 行首数字编号转 -
    text = re.sub(
        rf"({prefix})\s*\n((?:(?:\d+[\.．]|[-*])\s*.+\n?)+)",
        lambda m: m.group(1) + "\n\n" + re.sub(
            r"^(\d+)[\.．]\s*", r"- ", m.group(2), flags=re.M
        ),
        text,
    )
    return text


def _paragraph_with_subheadings(content: str) -> str:
    """处理段落内容：以「一、」「二、」等开头的行转为 ### 小标题，便于样式生效。"""
    if not content or not content.strip():
        return ""
    lines = content.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue
        if re.match(r"^[一二三四五六七八九十]+、", stripped):
            result.append(f"### {stripped}")
        else:
            result.append(stripped)
    return "\n\n".join(result).strip() + "\n\n"


def _parse_template_to_markdown(text: str) -> tuple[str, str | None]:
    """将 [标签] 格式解析为 Markdown。[主标题] 不输出到 content，单独返回供 ingest 用。

    Returns:
        (content, title): content 不含主标题；title 从 [主标题] 提取，无则为 None
    """
    if not text or not text.strip():
        return text, None

    blocks: list[tuple[str, str]] = []
    tag_pattern = r"主标题|副标题|作者|摘要|导语|段落标题|段落|引用|列表|分隔线|图片|结语|署名"
    # 使用 [^\[]* 而非 .*? 避免误匹配：内容截断到下一个 [ 之前
    pattern = rf"\[({tag_pattern})\]\s*\n?([^\[]*)"
    for m in re.finditer(pattern, text, re.DOTALL):
        tag, content = m.group(1), m.group(2).strip()
        if not content and tag != "分隔线":
            continue
        blocks.append((tag, content))

    if not blocks:
        return text.strip(), None

    main_title: str | None = None
    out: list[str] = []
    for tag, content in blocks:
        if tag == "主标题":
            # 主标题不输出到 content，仅提取供 ingest 用
            main_title = content
            continue
        elif tag == "副标题":
            out.append(f"### {content}\n")
        elif tag == "作者":
            out.append(f"*{content}*\n")
        elif tag == "摘要":
            out.append(f"{content}\n")
        elif tag == "导语":
            # 导语转为引用块，样式（blockquote）才能生效（背景色、左边框等）
            out.append(f"> {content}\n\n")
        elif tag == "段落":
            out.append(_paragraph_with_subheadings(content))
        elif tag == "段落标题":
            out.append(f"### {content}\n")
        elif tag == "引用":
            for line in content.split("\n"):
                if line.strip():
                    out.append(f"> {line.strip()}\n")
            out.append("\n")
        elif tag == "列表":
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("*"):
                    line = f"- {line}"
                if line:
                    out.append(f"{line}\n")
        elif tag == "分隔线":
            out.append("---\n")
        elif tag == "图片":
            out.append(f"![图片]({content})\n" if content else "")
        elif tag in ("结语", "署名"):
            out.append(f"\n{content}\n")

    return "".join(out).strip(), main_title


__all__ = ["normalize_to_wechat_format"]
