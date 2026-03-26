# Instalador do Reclame Aqui Bot para Windows.
#
# Este script prepara um ambiente isolado na pasta do projeto:
#   1. Valida que o Python 3.10+ esta instalado e disponivel no PATH.
#   2. Cria um virtualenv local em .venv.
#   3. Instala o pacote em modo editavel junto com suas dependencias.
#   4. Baixa o Chromium usado pelo Playwright.
#   5. Cria um .env a partir do .env.example, se ele ainda nao existir.
#
# Execute no PowerShell, preferencialmente como Administrador:
#   .\install.ps1

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$VenvDir    = Join-Path $ProjectDir ".venv"
$PythonExe  = Join-Path $VenvDir "Scripts\python.exe"
$EnvFile    = Join-Path $ProjectDir ".env"
$EnvExample = Join-Path $ProjectDir ".env.example"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Instalacao do Reclame Aqui Bot"                             -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pasta do projeto: $ProjectDir" -ForegroundColor Gray
Write-Host ""

Write-Host "[1/6] Verificando o Python instalado..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: Python nao foi encontrado no PATH." -ForegroundColor Red
    Write-Host "      Instale o Python 3.10+ em https://www.python.org/downloads/ e tente novamente." -ForegroundColor Red
    exit 1
}
Write-Host "      $pythonVersion" -ForegroundColor Green

Write-Host ""
Write-Host "[2/6] Criando o ambiente virtual (.venv)..." -ForegroundColor Yellow
if (Test-Path $VenvDir) {
    Write-Host "      .venv ja existe, pulando criacao." -ForegroundColor Gray
} else {
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual em $VenvDir" }
    Write-Host "      .venv criado em $VenvDir" -ForegroundColor Green
}

Write-Host ""
Write-Host "[3/6] Atualizando pip..." -ForegroundColor Yellow
& $PythonExe -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o pip" }
Write-Host "      pip atualizado." -ForegroundColor Green

Write-Host ""
Write-Host "[4/6] Instalando o pacote reclame-aqui-bot e suas dependencias..." -ForegroundColor Yellow
Push-Location $ProjectDir
try {
    & $PythonExe -m pip install -e . --quiet
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar o pacote" }
} finally {
    Pop-Location
}
Write-Host "      Pacote instalado em modo editavel." -ForegroundColor Green

Write-Host ""
Write-Host "[5/6] Instalando o Chromium usado pelo Playwright..." -ForegroundColor Yellow
Write-Host "      (este passo pode levar 1 a 2 minutos na primeira execucao)" -ForegroundColor Gray
& $PythonExe -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar o Chromium" }
Write-Host "      Chromium instalado." -ForegroundColor Green

Write-Host ""
Write-Host "[6/6] Verificando o arquivo .env..." -ForegroundColor Yellow
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "      .env criado a partir de .env.example." -ForegroundColor Green
        Write-Host "      ATENCAO: abra $EnvFile e preencha as credenciais reais antes de executar o bot." -ForegroundColor Yellow
    } else {
        Write-Host "      .env.example nao encontrado. Crie um .env manualmente." -ForegroundColor Yellow
    }
} else {
    Write-Host "      .env ja existe, mantendo o arquivo atual." -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Instalacao concluida"                                       -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Proximos passos:" -ForegroundColor White
Write-Host "  1. Edite o .env com as credenciais reais."                    -ForegroundColor White
Write-Host "  2. Rode um teste manual:            .\run.bat"                -ForegroundColor White
Write-Host "  3. Configure o agendamento:         .\setup-scheduler.ps1"    -ForegroundColor White
Write-Host ""
