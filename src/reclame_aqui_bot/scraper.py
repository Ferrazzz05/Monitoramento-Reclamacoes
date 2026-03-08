"""Scraper da página de reclamações do Reclame Aqui.

O scraper utiliza Playwright com o plugin de stealth para renderizar a página
da mesma forma que um navegador real. Essa é a única maneira confiável de
passar pela proteção do Cloudflare usada pelo Reclame Aqui.

A extração dos dados é feita a partir do JSON ``__NEXT_DATA__`` embutido no
HTML pelo Next.js, com um fallback para análise direta do DOM caso a
estrutura do JSON mude no futuro.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from playwright.sync_api import Page, sync_playwright
from playwright_stealth import Stealth

from reclame_aqui_bot.exceptions import CloudflareBlockedError, ScraperError
from reclame_aqui_bot.models import Complaint

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_BROWSER_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
)
_CLOUDFLARE_SIGNALS = ("blocked", "attention required", "just a moment")
_NEXT_DATA_PATTERN = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)
_PENDING_STATUS = "PENDING"
_MAX_RECURSION_DEPTH = 12


class ReclameAquiScraper:
    """Faz o scraping da aba de reclamações sem resposta de uma empresa."""

    def __init__(
        self,
        *,
        target_url: str,
        base_url: str,
        company_slug: str,
        headless: bool = True,
        initial_wait_seconds: int = 15,
        scroll_wait_seconds: int = 3,
        navigation_timeout_ms: int = 60_000,
    ) -> None:
        self._target_url = target_url
        self._base_url = base_url
        self._company_slug = company_slug
        self._headless = headless
        self._initial_wait_seconds = initial_wait_seconds
        self._scroll_wait_seconds = scroll_wait_seconds
        self._navigation_timeout_ms = navigation_timeout_ms

    def scrape(self) -> list[Complaint]:
        """Acessa a página alvo e retorna as reclamações sem resposta."""
        logger.info("Iniciando scraping de %s", self._target_url)
        try:
            with self._page_session() as page:
                self._navigate(page)
                self._guard_against_cloudflare(page)
                self._settle_page(page)
                return self._extract(page)
        except (CloudflareBlockedError, ScraperError):
            raise
        except Exception as exc:
            raise ScraperError(f"Falha inesperada no scraper: {exc}") from exc

    @contextmanager
    def _page_session(self) -> Iterator[Page]:
        stealth = Stealth()
        launch_args = list(_BROWSER_ARGS)
        viewport = {"width": 1920, "height": 1080}

        # Em modo visível (normalmente usado durante gravações ou debug),
        # posiciona a janela na metade esquerda da tela para deixar a outra
        # metade livre para o editor.
        if not self._headless:
            screen_size = _detect_screen_size()
            if screen_size is not None:
                screen_width, screen_height = screen_size
                window_width = screen_width // 2
                launch_args.append("--window-position=0,0")
                launch_args.append(f"--window-size={window_width},{screen_height}")
                viewport = {"width": window_width, "height": screen_height}

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=self._headless,
                args=launch_args,
            )
            try:
                context = browser.new_context(
                    viewport=viewport,
                    user_agent=_USER_AGENT,
                    locale="pt-BR",
                    timezone_id="America/Sao_Paulo",
                )
                stealth.apply_stealth_sync(context)
                page = context.new_page()
                yield page
            finally:
                browser.close()

    def _navigate(self, page: Page) -> None:
        try:
            page.goto(
                self._target_url,
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms,
            )
        except Exception as exc:
            raise ScraperError(f"Falha ao navegar para {self._target_url}: {exc}") from exc

        time.sleep(self._initial_wait_seconds)

    def _guard_against_cloudflare(self, page: Page) -> None:
        title = page.title().lower()
        if any(signal in title for signal in _CLOUDFLARE_SIGNALS):
            raise CloudflareBlockedError(
                f"Cloudflare bloqueou a requisição. Título da página: {title!r}"
            )

    def _settle_page(self, page: Page) -> None:
        """Rola a página para forçar o carregamento de conteúdo lazy-loaded."""
        page.evaluate("window.scrollBy(0, 500)")
        time.sleep(self._scroll_wait_seconds)
        page.evaluate("window.scrollBy(0, 500)")
        time.sleep(self._scroll_wait_seconds)

    def _extract(self, page: Page) -> list[Complaint]:
        html = page.content()

        all_items = self._extract_raw_items(html, page)
        if not all_items:
            logger.info("Nenhuma reclamação encontrada na página.")
            return []

        pending_items = [item for item in all_items if self._is_pending(item)]
        logger.info(
            "%d reclamação(ões) na página, das quais %d estão sem resposta",
            len(all_items),
            len(pending_items),
        )

        return [
            complaint
            for complaint in (self._build_complaint(item) for item in pending_items)
            if complaint is not None
        ]

    def _extract_raw_items(self, html: str, page: Page) -> list[dict[str, Any]]:
        items = self._parse_next_data(html)
        if items:
            logger.debug("Lista extraída via __NEXT_DATA__ (%d itens)", len(items))
            return items

        dom_items = self._parse_dom_items(page)
        if dom_items:
            logger.debug("Lista extraída via fallback DOM (%d itens)", len(dom_items))
            return dom_items

        logger.warning(
            "Nenhuma lista de reclamações foi encontrada. "
            "A estrutura da página pode ter mudado."
        )
        return []

    def _parse_next_data(self, html: str) -> list[dict[str, Any]]:
        match = _NEXT_DATA_PATTERN.search(html)
        if not match:
            return []

        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("Falha ao decodificar __NEXT_DATA__ como JSON")
            return []

        return self._find_complaints_list(payload)

    def _find_complaints_list(
        self,
        node: Any,
        depth: int = 0,
    ) -> list[dict[str, Any]]:
        """Localiza a lista ``complaints[tab]`` dentro do payload.

        O Reclame Aqui guarda as reclamações em ``complaints.LAST`` (aba
        "Últimas"), ``complaints.NOT_ANSWERED`` etc. A chave ativa é
        indicada pelo campo ``complaints.tab``.
        """
        if depth > _MAX_RECURSION_DEPTH:
            return []

        if isinstance(node, dict):
            complaints_section = node.get("complaints")
            if isinstance(complaints_section, dict):
                tab = complaints_section.get("tab")
                if isinstance(tab, str):
                    items = complaints_section.get(tab)
                    if isinstance(items, list):
                        return [item for item in items if isinstance(item, dict)]

            for value in node.values():
                found = self._find_complaints_list(value, depth + 1)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = self._find_complaints_list(item, depth + 1)
                if found:
                    return found

        return []

    @staticmethod
    def _is_pending(item: dict[str, Any]) -> bool:
        """Uma reclamação está ``sem resposta`` quando o status é ``PENDING``."""
        return str(item.get("status", "")).upper() == _PENDING_STATUS

    def _build_complaint(self, item: dict[str, Any]) -> Complaint | None:
        title = str(item.get("title") or "").strip()
        if not title:
            return None

        link = self._build_link(item)
        if not link:
            return None

        date = self._format_date(item.get("created") or item.get("createdAt") or "")

        try:
            return Complaint(title=title, link=link, date=date)
        except ValueError:
            return None

    def _build_link(self, item: dict[str, Any]) -> str:
        slug = item.get("url")
        if isinstance(slug, str) and slug:
            return f"{self._base_url}/{self._company_slug}/{slug}/"

        complaint_id = item.get("id")
        if complaint_id:
            return f"{self._base_url}/{self._company_slug}/{complaint_id}/"
        return ""

    @staticmethod
    def _format_date(raw: Any) -> str:
        if not isinstance(raw, str) or not raw:
            return ""
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
        return parsed.strftime("%d/%m/%Y %H:%M")

    def _parse_dom_items(self, page: Page) -> list[dict[str, Any]]:
        """Parser alternativo que varre o DOM quando o ``__NEXT_DATA__`` falha.

        Cada card de reclamação na página tem um badge de status em texto
        (``"Não respondida"``, ``"Respondida"`` etc.) que é usado para
        derivar ``status: "PENDING"`` nas entradas que estão sem resposta.
        """
        items: list[dict[str, Any]] = []
        seen_links: set[str] = set()

        for anchor in page.query_selector_all(f"a[href^='/{self._company_slug}/']"):
            try:
                href = anchor.get_attribute("href") or ""
                if not href or href == f"/{self._company_slug}/":
                    continue

                title = (anchor.inner_text() or "").strip()
                if not title or "ler reclama" in title.lower():
                    continue

                if href in seen_links:
                    continue
                seen_links.add(href)

                card = anchor.evaluate_handle(
                    "el => el.closest('[data-testid*=\"complaint\"],article,li,div')"
                )
                card_element = card.as_element() if card else None
                card_text = (card_element.inner_text() if card_element else "").lower()
                status = _PENDING_STATUS if "não respondida" in card_text else "ANSWERED"

                items.append({
                    "title": title,
                    "url": href.strip("/").split("/", 1)[-1] if "/" in href else href,
                    "id": "",
                    "status": status,
                })
            except Exception as exc:
                logger.debug("Falha ao parsear âncora do DOM: %s", exc)
                continue

        return items


def _detect_screen_size() -> tuple[int, int] | None:
    """Retorna ``(largura, altura)`` da tela principal no Windows."""
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return None
