"""
fastfish-lite 项目配置模块。

精简版：不含微信、激活、百度、千帆相关配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_project_root = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    """全局配置对象。"""

    db_path: Path
    images_base_path: Path
    api_host: str = "0.0.0.0"
    api_port: int = 8899
    allow_local_no_auth: bool = True
    api_key: str | None = None
    api_base_url: str = ""
    log_dir: Path | None = None


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_from_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """读取配置并缓存。"""
    project_root = Path(__file__).resolve().parent

    db_path_env = os.getenv("MEDIA_AGENT_DB_PATH")
    if db_path_env:
        db_path = Path(db_path_env).expanduser().resolve()
    else:
        db_path = (project_root / "data" / "media_agent.db").resolve()

    images_base_env = os.getenv("MEDIA_AGENT_IMAGES_BASE")
    if images_base_env:
        images_base = Path(images_base_env).expanduser().resolve()
    else:
        default_path = project_root / "data" / "images"
        if default_path.exists() and default_path.is_dir():
            images_base = default_path.resolve()
        else:
            import tempfile
            temp_images = Path(tempfile.gettempdir()) / "fastfish_lite_images"
            temp_images.mkdir(parents=True, exist_ok=True)
            images_base = temp_images.resolve()

    api_host = os.getenv("MEDIA_AGENT_API_HOST", "0.0.0.0")
    api_port = _int_from_env("MEDIA_AGENT_API_PORT", 8899)
    allow_local_no_auth = _bool_from_env("MEDIA_AGENT_ALLOW_LOCAL_NO_AUTH", True)
    api_key = os.getenv("MEDIA_AGENT_API_KEY")
    _base = (os.getenv("MEDIA_AGENT_BASE_URL") or os.getenv("FASTFISH_BASE_URL") or "").strip()
    api_base_url = _base or f"http://127.0.0.1:{api_port}"

    log_dir_env = os.getenv("MEDIA_AGENT_LOG_DIR")
    if log_dir_env:
        log_dir = Path(log_dir_env).expanduser().resolve()
    else:
        log_dir = (db_path.parent / "logs").resolve()

    return Settings(
        db_path=db_path,
        images_base_path=images_base,
        api_host=api_host,
        api_port=api_port,
        allow_local_no_auth=allow_local_no_auth,
        api_key=api_key,
        api_base_url=api_base_url,
        log_dir=log_dir,
    )


__all__ = ["Settings", "get_settings"]
