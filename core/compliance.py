"""
fastfish-lite 合规检测模块。

仅敏感词检测，原创度返回「需商业版」。
"""

from __future__ import annotations

from typing import Any

from core.sensitive import check_content_compliance_with_status


def _build_sens_failed_checks(sens_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "sensitive": {
            "performed": sens_status.get("performed", False),
            "sources": sens_status.get("sources", ""),
            "skipped_reason": sens_status.get("skipped_reason", ""),
            "matched": sens_status.get("matched", []),
            "failed_categories": sens_status.get("failed_categories", []),
            "suggestion": "请修改或删除上述敏感词后重试",
        },
        "originality": {"performed": False, "skipped_reason": "原创度检测需商业版"},
    }


def check_compliance_for_content(title: str, content: str) -> dict[str, Any]:
    """对标题和正文执行敏感词检测。原创度返回「需商业版」。

    Returns:
        ok, passed, message, checks, checks_summary, user_facing_summary
    """
    row = {"rewritten_title": title or "", "rewritten_content": content or ""}
    passed_sens, err_sens, sens_status = check_content_compliance_with_status(row)
    if not passed_sens:
        checks = _build_sens_failed_checks(sens_status)
        return {
            "ok": True,
            "passed": False,
            "message": err_sens,
            "checks": checks,
            "checks_summary": {"sensitive": f"敏感词检测未通过：{err_sens}", "originality": "未执行"},
            "user_facing_summary": f"敏感词检测未通过：{err_sens}。请修改或删除上述敏感词后重试。",
        }
    sens_performed = sens_status.get("performed", False)
    sens_sources = sens_status.get("sources", "skipped")
    sens_summary = f"敏感词检测已执行（{sens_sources}），通过" if sens_performed else "敏感词检测未执行"
    orig_summary = "原创度检测需商业版，请联系获取完整版 fastfish"
    checks = {
        "sensitive": {
            "performed": sens_performed,
            "sources": sens_sources,
            "skipped_reason": sens_status.get("skipped_reason", ""),
        },
        "originality": {"performed": False, "skipped_reason": "需商业版"},
    }
    user_facing = f"{sens_summary}。{orig_summary}"
    return {
        "ok": True,
        "passed": True,
        "message": "",
        "checks": checks,
        "checks_summary": {"sensitive": sens_summary, "originality": orig_summary},
        "user_facing_summary": user_facing,
    }
