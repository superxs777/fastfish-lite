"""
fastfish-lite 敏感词检测模块。

仅支持本地 DFA 词库，不含百度内容审核 API。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CATEGORY_FILES: dict[str, list[str]] = {
    "ad": ["广告类型.txt"],
    "porn": ["色情类型.txt", "色情词库.txt"],
    "political": ["政治类型.txt", "反动词库.txt"],
    "abuse": ["补充词库.txt", "其他词库.txt"],
}

CATEGORY_NAMES: dict[str, str] = {
    "ad": "广告垃圾",
    "porn": "色情垃圾",
    "political": "违禁涉政",
    "abuse": "谩骂灌水",
}


def _strip_html(html: str) -> str:
    if not html or not str(html).strip():
        return ""
    text = re.sub(r"<[^>]+>", "", str(html))
    text = re.sub(r"\s+", " ", text).strip()
    return text


class DFAMatcher:
    """DFA 敏感词匹配器。"""

    def __init__(self, words: list[str]) -> None:
        self._root: dict[str, Any] = {}
        for w in words:
            w = (w or "").strip()
            if not w:
                continue
            node = self._root
            for c in w:
                if c not in node:
                    node[c] = {}
                node = node[c]
            node["__end__"] = True

    def search(self, text: str) -> list[tuple[int, int, str]]:
        if not text:
            return []
        result: list[tuple[int, int, str]] = []
        n = len(text)
        i = 0
        while i < n:
            node = self._root
            j = i
            matched_word: list[str] = []
            last_end = -1
            while j < n and text[j] in node:
                matched_word.append(text[j])
                node = node[text[j]]
                j += 1
                if node.get("__end__"):
                    last_end = j
            if last_end > 0:
                word = "".join(matched_word[: last_end - i])
                result.append((i, last_end, word))
                i = last_end
            else:
                i += 1
        return result


def _load_words_from_file(path: Path) -> list[str]:
    words: list[str] = []
    if not path.exists() or not path.is_file():
        return words
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                words.append(w)
    except Exception as e:
        logger.warning(f"读取敏感词文件失败: {path}, {e}")
    return words


class SensitiveChecker:
    """敏感词检测器。仅本地 DFA，无百度。"""

    def __init__(self, vocabulary_dir: Path | None = None) -> None:
        if vocabulary_dir is None:
            env_path = os.getenv("MEDIA_AGENT_SENSITIVE_LEXICON_DIR")
            if env_path:
                vocabulary_dir = Path(env_path).expanduser().resolve()
            else:
                project_root = Path(__file__).resolve().parent.parent
                vocabulary_dir = project_root / "data" / "sensitive_lexicon" / "Vocabulary"
        self.vocabulary_dir = Path(vocabulary_dir).resolve()
        self._matchers: dict[str, DFAMatcher] = {}
        self._loaded = False

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return len(self._matchers) > 0
        if not self.vocabulary_dir.exists() or not self.vocabulary_dir.is_dir():
            logger.warning(
                f"敏感词库目录不存在: {self.vocabulary_dir}，跳过敏感词检测。"
                "请将词库拷到 data/sensitive_lexicon/Vocabulary/"
            )
            self._loaded = True
            return False
        for cat, files in CATEGORY_FILES.items():
            all_words: list[str] = []
            for fname in files:
                fpath = self.vocabulary_dir / fname
                words = _load_words_from_file(fpath)
                all_words.extend(words)
            if all_words:
                self._matchers[cat] = DFAMatcher(all_words)
        self._loaded = True
        return len(self._matchers) > 0

    def check(self, title: str, content_html: str) -> dict[str, Any]:
        content_text = _strip_html(content_html or "")
        title = (title or "").strip()
        local_loaded = self._ensure_loaded()
        if local_loaded:
            matched: list[dict[str, str]] = []
            failed_categories: list[str] = []
            for cat, matcher in self._matchers.items():
                cat_name = CATEGORY_NAMES.get(cat, cat)
                for start, end, word in matcher.search(title):
                    matched.append({"category": cat, "category_name": cat_name, "word": word, "in": "title"})
                    if cat not in failed_categories:
                        failed_categories.append(cat)
                for start, end, word in matcher.search(content_text):
                    matched.append({"category": cat, "category_name": cat_name, "word": word, "in": "content"})
                    if cat not in failed_categories:
                        failed_categories.append(cat)
            if matched:
                words_preview = [m["word"] for m in matched[:5]]
                if len(matched) > 5:
                    words_preview.append("...")
                msg = f"内容含敏感词，涉及：{', '.join(CATEGORY_NAMES.get(c, c) for c in failed_categories)}，示例：{', '.join(words_preview)}"
                return {
                    "passed": False, "message": msg, "failed_categories": failed_categories, "matched": matched,
                    "performed": True, "sources": "local", "skipped_reason": "",
                }
        if local_loaded:
            return {
                "passed": True, "message": "", "failed_categories": [], "matched": [],
                "performed": True, "sources": "local", "skipped_reason": "",
            }
        return {
            "passed": True, "message": "", "failed_categories": [], "matched": [],
            "performed": False, "sources": "skipped",
            "skipped_reason": "本地词库不存在，请配置 data/sensitive_lexicon/Vocabulary/",
        }


_checker: SensitiveChecker | None = None


def get_checker(vocabulary_dir: Path | None = None) -> SensitiveChecker:
    global _checker
    if _checker is None:
        _checker = SensitiveChecker(vocabulary_dir)
    return _checker


def check_content_compliance_with_status(row: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """检查内容是否通过敏感词检测。"""
    title = row.get("rewritten_title") or ""
    content = row.get("rewritten_content") or ""
    result = get_checker().check(title, content)
    status = {
        "performed": result.get("performed", False),
        "sources": result.get("sources", "skipped"),
        "skipped_reason": result.get("skipped_reason", ""),
    }
    if result["passed"]:
        return True, "", status
    status["matched"] = result.get("matched", [])
    status["failed_categories"] = result.get("failed_categories", [])
    return False, result["message"], status
