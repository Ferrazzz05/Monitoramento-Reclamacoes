"""Carregamento de configurações a partir de variáveis de ambiente e do arquivo ``.env``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from reclame_aqui_bot.exceptions import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    """Snapshot imutável de todas as opções configuráveis do bot."""

    gmail_user: str
    gmail_app_password: str
    recipients: tuple[str, ...]
    error_recipient: str
    company_slug: str
    company_name: str
    start_hour: int
    end_hour: int
    headless: bool
    log_level: str
    db_path: Path
    log_path: Path

    @property
    def target_url(self) -> str:
        return (
            f"https://www.reclameaqui.com.br/empresa/"
            f"{self.company_slug}/lista-reclamacoes/"
        )

    @property
    def base_url(self) -> str:
        return "https://www.reclameaqui.com.br"


def load_settings(env_file: Path | None = None) -> Settings:
    """Lê as configurações do ambiente e retorna um ``Settings`` imutável.

    Levanta ``ConfigError`` se alguma variável obrigatória estiver ausente ou inválida.
    """
    env_path = env_file or (PROJECT_ROOT / ".env")
    if env_path.exists():
        load_dotenv(env_path)

    try:
        gmail_user = _require("GMAIL_USER")
        gmail_app_password = _require("GMAIL_APP_PASSWORD")
        recipients_raw = _require("RECIPIENTS")
        company_slug = _require("COMPANY_SLUG")
        company_name = _require("COMPANY_NAME")
    except KeyError as exc:
        raise ConfigError(f"Variável de ambiente obrigatória não definida: {exc}") from exc

    recipients = tuple(r.strip() for r in recipients_raw.split(",") if r.strip())
    if not recipients:
        raise ConfigError("RECIPIENTS deve conter ao menos um email")

    start_hour = _int_env("START_HOUR", 7)
    end_hour = _int_env("END_HOUR", 18)
    if not 0 <= start_hour < end_hour <= 24:
        raise ConfigError(
            f"Intervalo inválido: START_HOUR={start_hour}, END_HOUR={end_hour}. "
            "Esperado 0 <= START_HOUR < END_HOUR <= 24."
        )

    return Settings(
        gmail_user=gmail_user,
        gmail_app_password=gmail_app_password,
        recipients=recipients,
        error_recipient=os.environ.get("ERROR_RECIPIENT", gmail_user),
        company_slug=company_slug,
        company_name=company_name,
        start_hour=start_hour,
        end_hour=end_hour,
        headless=_bool_env("HEADLESS", True),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        db_path=PROJECT_ROOT / "data" / "notified.db",
        log_path=PROJECT_ROOT / "logs" / "bot.log",
    )


def _require(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise KeyError(key)
    return value


def _int_env(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} deve ser um inteiro válido, recebido: {raw!r}") from exc


def _bool_env(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
