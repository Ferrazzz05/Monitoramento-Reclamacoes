@echo off
REM Launcher do Reclame Aqui Bot usado pelo Agendador de Tarefas do Windows.
REM Garante que o diretorio de trabalho seja a pasta do projeto antes de rodar.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: ambiente virtual nao encontrado em .venv
    echo Execute install.ps1 antes de rodar este script.
    exit /b 1
)

.venv\Scripts\python.exe -m reclame_aqui_bot
exit /b %ERRORLEVEL%
