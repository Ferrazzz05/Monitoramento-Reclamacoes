"""Configuração do logging com handler de arquivo rotativo."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3


def configure_logging(log_path: Path, level: str = "INFO") -> None:
    """Configura o logger raiz com um arquivo rotativo e saída para o console."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Força UTF-8 no stdout para evitar mojibake em consoles do Windows
    # que ainda usam code pages legadas (cp1252).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    # O logger do Playwright é muito verboso em nível INFO.
    logging.getLogger("playwright").setLevel(logging.WARNING)
