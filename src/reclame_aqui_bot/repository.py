"""Repositório SQLite usado para deduplicar notificações entre execuções."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from reclame_aqui_bot.exceptions import PersistenceError
from reclame_aqui_bot.models import Complaint

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notified_complaints (
    link        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    date        TEXT,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

_INSERT = (
    "INSERT OR IGNORE INTO notified_complaints (link, title, date) VALUES (?, ?, ?)"
)


class NotifiedRepository:
    """Registra quais reclamações o bot já notificou.

    O ``link`` é usado como chave primária porque identifica unicamente uma
    reclamação no Reclame Aqui e é estável ao longo do tempo.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def is_notified(self, link: str) -> bool:
        """Verifica se uma reclamação já foi notificada."""
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM notified_complaints WHERE link = ? LIMIT 1",
                    (link,),
                )
                return cursor.fetchone() is not None
        except sqlite3.Error as exc:
            raise PersistenceError(f"Falha ao consultar {link}: {exc}") from exc

    def mark_notified(self, complaint: Complaint) -> None:
        """Registra uma reclamação como notificada."""
        try:
            with self._connect() as conn:
                conn.execute(_INSERT, (complaint.link, complaint.title, complaint.date))
        except sqlite3.Error as exc:
            raise PersistenceError(f"Falha ao registrar {complaint.link}: {exc}") from exc

    def mark_many_notified(self, complaints: Sequence[Complaint]) -> None:
        """Registra várias reclamações de uma vez, em uma única transação."""
        if not complaints:
            return
        rows = [(c.link, c.title, c.date) for c in complaints]
        try:
            with self._connect() as conn:
                conn.executemany(_INSERT, rows)
        except sqlite3.Error as exc:
            raise PersistenceError(
                f"Falha ao registrar lote de {len(rows)} reclamações: {exc}"
            ) from exc

    def filter_new(self, complaints: Sequence[Complaint]) -> list[Complaint]:
        """Retorna apenas as reclamações que ainda não foram notificadas."""
        if not complaints:
            return []
        return [c for c in complaints if not self.is_notified(c.link)]

    def _initialize(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(_SCHEMA)
        except sqlite3.Error as exc:
            raise PersistenceError(
                f"Falha ao inicializar banco de dados em {self._db_path}: {exc}"
            ) from exc

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
