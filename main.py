"""
fastfish-lite 程序入口。

开源精简版：无激活检查，直接启动 FastAPI。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

import uvicorn

from api.server import app
from config import get_settings
from core.db import init_database


def setup_logging() -> None:
    """配置日志格式与级别。"""
    from config import get_settings

    log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in root.handlers[:]:
        root.removeHandler(h)

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter(log_fmt, datefmt=date_fmt))
    root.addHandler(sh)

    settings = get_settings()
    if settings.log_dir:
        try:
            settings.log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if settings.log_dir.exists():
            app_log = settings.log_dir / "fastfish_lite.log"
            fh = logging.FileHandler(app_log, encoding="utf-8")
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter(log_fmt, datefmt=date_fmt))
            root.addHandler(fh)
            err_log = settings.log_dir / "fastfish_lite_error.log"
            eh = logging.FileHandler(err_log, encoding="utf-8")
            eh.setLevel(logging.ERROR)
            eh.setFormatter(logging.Formatter(log_fmt, datefmt=date_fmt))
            root.addHandler(eh)


def bootstrap() -> None:
    """初始化应用运行所需的基础设施。"""
    setup_logging()
    logger = logging.getLogger(__name__)
    settings = get_settings()
    init_database()
    logger.info(f"Database initialized at: {settings.db_path}")


def main() -> None:
    """命令行入口：bootstrap 后启动 FastAPI。"""
    bootstrap()
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
