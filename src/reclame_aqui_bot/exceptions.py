"""Hierarquia de exceções customizadas do bot."""


class BotError(Exception):
    """Classe base para qualquer erro levantado pelo bot."""


class ConfigError(BotError):
    """Levantada quando uma configuração obrigatória está ausente ou inválida."""


class ScraperError(BotError):
    """Levantada quando o scraper falha em carregar ou parsear a página."""


class CloudflareBlockedError(ScraperError):
    """Levantada quando o Cloudflare intercepta a requisição."""


class EmailError(BotError):
    """Levantada quando o envio de email falha."""


class PersistenceError(BotError):
    """Levantada quando o repositório de notificações falha."""
