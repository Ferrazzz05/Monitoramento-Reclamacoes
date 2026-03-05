"""Permite executar o pacote diretamente com ``python -m reclame_aqui_bot``."""

import sys

from reclame_aqui_bot.service import run

if __name__ == "__main__":
    sys.exit(run())
