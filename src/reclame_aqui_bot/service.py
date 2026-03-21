"""Orquestrador da aplicação: conecta os componentes e executa o pipeline."""

from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime

from reclame_aqui_bot.config import Settings, load_settings
from reclame_aqui_bot.exceptions import ConfigError
from reclame_aqui_bot.logging_setup import configure_logging
from reclame_aqui_bot.notifier import GmailNotifier
from reclame_aqui_bot.repository import NotifiedRepository
from reclame_aqui_bot.scraper import ReclameAquiScraper

logger = logging.getLogger(__name__)

_EXIT_OK = 0
_EXIT_FAILURE = 1
_SUNDAY = 6
_SEPARATOR = "=" * 60


def run() -> int:
    """Ponto de entrada chamado pelo console script ``reclame-aqui-bot``.

    Retorna um código de saída adequado para agendadores do sistema
    operacional: ``0`` em caso de sucesso ou quando a execução é pulada
    (fora do horário comercial) e ``1`` em caso de falha.
    """
    try:
        settings = load_settings()
    except ConfigError as exc:
        # O logging ainda não foi configurado aqui, então caímos para stderr.
        print(f"[config] {exc}", file=sys.stderr)
        return _EXIT_FAILURE

    configure_logging(settings.log_path, level=settings.log_level)
    logger.info(_SEPARATOR)
    logger.info("Iniciando execução do bot")

    if not _is_business_hours(datetime.now(), settings):
        logger.info(
            "Fora do horário comercial (%dh–%dh, Seg–Sáb). Encerrando.",
            settings.start_hour,
            settings.end_hour,
        )
        return _EXIT_OK

    notifier = GmailNotifier(
        user=settings.gmail_user,
        app_password=settings.gmail_app_password,
    )

    try:
        _execute_pipeline(settings, notifier)
        return _EXIT_OK
    except Exception as exc:
        _handle_failure(exc, notifier, settings)
        return _EXIT_FAILURE
    finally:
        logger.info("Execução finalizada")
        logger.info(_SEPARATOR)


def _execute_pipeline(settings: Settings, notifier: GmailNotifier) -> None:
    repository = NotifiedRepository(settings.db_path)
    scraper = ReclameAquiScraper(
        target_url=settings.target_url,
        base_url=settings.base_url,
        company_slug=settings.company_slug,
        headless=settings.headless,
    )

    complaints = scraper.scrape()
    logger.info("Scraper retornou %d reclamação(ões) sem resposta", len(complaints))

    if not complaints:
        logger.info("Nenhuma reclamação sem resposta encontrada.")
        return

    new_complaints = repository.filter_new(complaints)
    logger.info("Após filtrar duplicatas: %d nova(s)", len(new_complaints))

    if not new_complaints:
        logger.info("Todas as reclamações já foram notificadas anteriormente.")
        return

    notifier.send_complaint_alert(
        new_complaints,
        recipients=settings.recipients,
        company_name=settings.company_name,
    )
    repository.mark_many_notified(new_complaints)
    logger.info(
        "Alerta enviado e %d reclamação(ões) registrada(s) como notificada(s).",
        len(new_complaints),
    )


def _handle_failure(
    exc: Exception,
    notifier: GmailNotifier,
    settings: Settings,
) -> None:
    error_details = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
    logger.error("Erro durante a execução:\n%s", error_details)

    try:
        notifier.send_error_alert(
            error_details,
            recipient=settings.error_recipient,
            component=type(exc).__name__,
        )
    except Exception as email_exc:
        logger.error("Falha ao enviar o email de erro: %s", email_exc)


def _is_business_hours(now: datetime, settings: Settings) -> bool:
    if now.weekday() == _SUNDAY:
        return False
    return settings.start_hour <= now.hour < settings.end_hour
