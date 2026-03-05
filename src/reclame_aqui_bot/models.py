"""Modelos de domínio do bot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Complaint:
    """Representa uma reclamação publicada no Reclame Aqui."""

    title: str
    link: str
    date: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Complaint.title não pode estar vazio")
        if not self.link.strip():
            raise ValueError("Complaint.link não pode estar vazio")
