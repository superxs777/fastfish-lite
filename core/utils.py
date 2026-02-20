"""
fastfish-lite 工具函数。

包含封面图验证等与发布无关的通用逻辑。
"""

from __future__ import annotations

import os
from pathlib import Path


def validate_cover_image_path(pic: str, images_base_path: Path) -> tuple[bool, str | None]:
    """验证封面图路径是否有效。

    Args:
        pic: 封面图路径或 URL
        images_base_path: 图片基础路径

    Returns:
        (是否有效, 错误信息)
    """
    if not pic or not str(pic).strip():
        return False, "封面图路径为空"

    raw = str(pic).strip()
    if raw.startswith(("http://", "https://")):
        return True, None

    path = Path(raw)
    if not path.is_absolute():
        path = images_base_path / raw

    if not path.exists():
        return False, f"文件不存在: {path}"
    if not path.is_file():
        return False, f"不是文件（可能是目录）: {path}"
    try:
        if not os.access(path, os.R_OK):
            return False, f"文件无读取权限: {path}"
    except Exception as e:
        return False, f"权限检查失败: {str(e)}"
    try:
        file_size = path.stat().st_size
        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            return False, f"文件过大（{file_size / 1024 / 1024:.2f}MB），最大支持 10MB: {path}"
    except Exception as e:
        return False, f"获取文件大小失败: {str(e)}"
    return True, None
