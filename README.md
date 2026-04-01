# Reclame Aqui Bot

Bot de monitoramento que acessa a página de uma empresa no Reclame Aqui de hora em
hora, identifica reclamações que ainda não foram respondidas e envia um alerta por
email para o time responsável. Foi construído para substituir uma automação em N8N
que sofria com alertas falsos e mensagens duplicadas.

## O problema

A primeira versão desse monitor foi construída em N8N, encadeando FireCrawl para o
scraping e um LLM (Gemini) para interpretar o HTML e extrair as reclamações. Na
prática o fluxo sofria com três problemas recorrentes:

1. **Falsos positivos.** O modelo ocasionalmente classificava como "sem resposta"
   reclamações que já haviam sido respondidas, gerando alertas incorretos.
2. **Alertas duplicados.** A automação não tinha memória entre execuções; toda
   reclamação ainda pendente era notificada novamente a cada hora.
3. **Custo e fragilidade.** Cada execução consumia créditos do FireCrawl e do
   Gemini, além de estar exposta a mudanças de layout que quebravam o parser
   baseado em linguagem natural.

## A solução

Esta versão é um aplicativo Python autônomo que elimina completamente a
dependência de serviços pagos e de LLMs. O pipeline de cada execução:

1. **Verifica o horário comercial.** Fora desse intervalo (e aos domingos) a
   execução é encerrada imediatamente com código de saída zero.
2. **Abre a página com Playwright + stealth.** A renderização de um navegador
   real é a forma mais confiável de passar pela proteção Cloudflare do site.
3. **Extrai dados estruturados do `__NEXT_DATA__`.** O Reclame Aqui é construído
   em Next.js e serializa todo o estado da página em um JSON embutido no HTML.
   O bot navega até `props.pageProps.complaints[tab]` (onde `tab` é o campo
   que indica qual aba está ativa, normalmente ``LAST``) e lê diretamente
   título, data, status, ID e URL de cada reclamação. Não há interpretação
   de linguagem natural envolvida.
4. **Filtra pelo status ``PENDING``.** A aba "Últimas" traz tanto reclamações
   respondidas quanto pendentes. O bot filtra localmente apenas as que têm
   status ``PENDING``, o que evita o atraso de indexação que existe no filtro
   server-side ``?status=NOT_ANSWERED``.
5. **Deduplica no SQLite.** Cada reclamação já notificada é registrada por
   `link` (chave primária). Em execuções subsequentes, apenas itens realmente
   novos são considerados.
6. **Envia o email via Gmail SMTP.** Usa um App Password e formata o corpo em
   HTML com um card por reclamação.
7. **Trata falhas com um segundo email.** Se qualquer etapa do pipeline lançar
   exceção, um email de erro com traceback é enviado para um destinatário
   técnico.

## Arquitetura

```
┌───────────────┐
│  service.py   │  orquestrador + tratamento de erros
└──────┬────────┘
       │
       ▼
┌───────────────┐      ┌────────────────┐      ┌───────────────┐
│  scraper.py   │────► │ repository.py  │────► │  notifier.py  │
│  (Playwright) │      │   (SQLite)     │      │  (Gmail SMTP) │
└───────────────┘      └────────────────┘      └───────────────┘
```

Cada componente é uma classe independente, injetada pelo `service.py`. As
configurações vêm de um `Settings` imutável carregado do `.env`, e erros
específicos são modelados por uma hierarquia de exceções (`BotError` e filhos)
que permitem tratamento granular quando necessário.

## Stack técnica

- **Python 3.10+** com type hints em todos os módulos.
- **Playwright** para automação do Chromium em modo headless.
- **playwright-stealth** para mascarar sinais de automação e passar pelo
  Cloudflare.
- **SQLite** (stdlib) para o controle de reclamações já notificadas.
- **smtplib** (stdlib) para o envio de email via Gmail SMTP.
- **python-dotenv** para carregar as variáveis de ambiente.
- **hatchling** como build backend (PEP 517).

Empacotamento segue o layout `src/`, com entry point CLI exposto via
`[project.scripts]` no `pyproject.toml`.

## Estrutura do projeto

```
bot_python/
├── .env.example             Template de configuração
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml           Metadados, dependências e entry points
├── install.ps1              Instalador para Windows
├── run.bat                  Launcher chamado pelo Agendador de Tarefas
├── setup-scheduler.ps1      Registra a tarefa agendada
├── data/                    Banco SQLite (gerado em runtime)
├── logs/                    Arquivo de log rotativo (gerado em runtime)
└── src/reclame_aqui_bot/
    ├── __init__.py
    ├── __main__.py          Entry point (python -m reclame_aqui_bot)
    ├── config.py            Settings (dataclass) e loader do .env
    ├── exceptions.py        Hierarquia de erros
    ├── logging_setup.py     Configuração do logger com rotação
    ├── models.py            Domain model: Complaint
    ├── notifier.py          GmailNotifier (SMTP + templates HTML)
    ├── repository.py        NotifiedRepository (SQLite)
    ├── scraper.py           ReclameAquiScraper (Playwright + stealth)
    └── service.py           Orquestrador + pipeline
```

## Requisitos

- Windows 10/11 (o agendamento usa o Task Scheduler; o código Python em si é
  multiplataforma)
- Python 3.10 ou superior
- Uma conta Gmail com verificação em duas etapas ativa e uma
  [App Password](https://myaccount.google.com/apppasswords) gerada
- Conexão estável com a internet

## Instalação

Clone o repositório em qualquer pasta local:

```powershell
git clone https://github.com/SEU-USUARIO/reclame-aqui-bot.git
cd reclame-aqui-bot
```

Rode o instalador (como Administrador):

```powershell
.\install.ps1
```

O instalador cria um `.venv` local, instala o pacote em modo editável e baixa
o Chromium usado pelo Playwright. Se o PowerShell bloquear a execução do
script, libere a política atual uma única vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Configuração

Copie o template e preencha com os valores reais:

```powershell
copy .env.example .env
notepad .env
```

| Variável             | Obrigatória | Descrição                                                                 |
| -------------------- | ----------- | ------------------------------------------------------------------------- |
| `GMAIL_USER`         | sim         | Email remetente (precisa ter verificação em 2 etapas).                    |
| `GMAIL_APP_PASSWORD` | sim         | App Password gerada em https://myaccount.google.com/apppasswords.         |
| `RECIPIENTS`         | sim         | Lista de destinatários separados por vírgula.                             |
| `ERROR_RECIPIENT`    | não         | Destinatário dos emails de erro. Padrão: o mesmo `GMAIL_USER`.            |
| `COMPANY_SLUG`       | sim         | Slug da empresa na URL do Reclame Aqui (ex: `empresa-exemplo`).           |
| `COMPANY_NAME`       | sim         | Nome da empresa usado no corpo do email.                                  |
| `START_HOUR`         | não         | Hora inicial do horário comercial. Padrão: `7`.                           |
| `END_HOUR`           | não         | Hora final (exclusiva) do horário comercial. Padrão: `18`.                |
| `HEADLESS`           | não         | `true` para rodar o Chromium sem janela. Padrão: `true`.                  |
| `LOG_LEVEL`          | não         | Nível de log (`DEBUG`, `INFO`, `WARNING`, ...). Padrão: `INFO`.           |

## Execução

Teste manualmente antes de agendar:

```powershell
.\run.bat
```

Saída esperada em uma execução típica:

```
2026-04-16 09:19:13 [INFO] Iniciando scraping de https://www.reclameaqui.com.br/...
2026-04-16 09:19:37 [INFO] 5 reclamação(ões) na página, das quais 1 estão sem resposta
2026-04-16 09:19:37 [INFO] Após filtrar duplicatas: 1 nova(s)
2026-04-16 09:19:41 [INFO] Email enviado para 4 destinatário(s)
2026-04-16 09:19:41 [INFO] Alerta enviado e 1 reclamação(ões) registrada(s) como notificada(s).
```

O mesmo executável pode ser invocado via:

```powershell
python -m reclame_aqui_bot
```

## Agendamento no Windows

Registre a tarefa no Task Scheduler (como Administrador):

```powershell
.\setup-scheduler.ps1
```

O script cria uma tarefa chamada `ReclameAquiBot` que dispara das 7h às 17h em
todos os dias. O próprio bot ignora execuções aos domingos e fora do intervalo
definido no `.env`, então a tarefa pode rodar com segurança mesmo em dias
não úteis.

Comandos úteis:

```powershell
# Forçar uma execução imediata
Start-ScheduledTask -TaskName 'ReclameAquiBot'

# Consultar o status da última execução
Get-ScheduledTaskInfo -TaskName 'ReclameAquiBot'

# Remover o agendamento
Unregister-ScheduledTask -TaskName 'ReclameAquiBot' -Confirm:$false
```

## Como os dados são persistidos

O estado do bot entre execuções é mantido em `data/notified.db`, um SQLite com
uma única tabela:

```sql
CREATE TABLE notified_complaints (
    link        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    date        TEXT,
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Para reiniciar o histórico e forçar o bot a renotificar todas as reclamações
ainda pendentes, basta apagar o arquivo. Ele é recriado automaticamente na
próxima execução.

## Observabilidade

Os logs ficam em `logs/bot.log` com rotação automática (2 MB por arquivo, 3
backups). Um mesmo log é emitido também no stdout, o que torna as execuções
manuais fáceis de acompanhar.

Exemplo do comportamento desejado quando não há novidades:

```
5 reclamação(ões) na página, das quais 1 estão sem resposta
Após filtrar duplicatas: 0 nova(s)
Todas as reclamações já foram notificadas anteriormente.
```

Esse é justamente o cenário que a versão em N8N não conseguia cobrir: detectar
uma reclamação pendente sem enviar o mesmo alerta repetidamente.

## Decisões técnicas

Algumas escolhas que moldaram o projeto e vale registrar:

- **Ler a aba "Últimas" em vez de um filtro server-side.** O filtro
  ``?status=NOT_ANSWERED`` do Reclame Aqui sofre com atraso de indexação, o
  que fazia o bot não enxergar reclamações recém-publicadas por vários
  minutos. A aba "Últimas" é atualizada em tempo real; o filtro por status
  é feito no cliente, a partir do campo ``status`` de cada item.
- **Extração estruturada, sem LLM.** O Next.js serializa o estado completo da
  página em `__NEXT_DATA__`. Ler esse JSON é determinístico, rápido e barato,
  o oposto de pedir a um modelo para "adivinhar" quais reclamações estão sem
  resposta a partir do texto renderizado.
- **Stealth ao invés de API.** O Reclame Aqui expõe algumas APIs internas,
  mas todas passam por Cloudflare e bloqueiam chamadas diretas. Um navegador
  real com sinais de automação mascarados continua sendo a forma mais
  estável de acessar a página.
- **Estado local em SQLite.** A deduplicação poderia ser feita em um Redis
  ou Postgres, mas para um bot que roda uma vez por hora em uma única
  máquina, SQLite oferece durabilidade suficiente, zero dependências externas
  e backup trivial (basta copiar o arquivo).
- **Configuração obrigatória.** `COMPANY_SLUG`, `COMPANY_NAME`, `GMAIL_USER`,
  `GMAIL_APP_PASSWORD` e `RECIPIENTS` não têm valores padrão; a ausência
  levanta `ConfigError` antes de qualquer outra etapa rodar. Isso evita
  surpresas em deploys e deixa o contrato do `.env` explícito.
- **Tratamento de falhas com notificação.** Qualquer exceção não tratada dispara
  um email de erro com o traceback completo. Fica difícil o bot falhar em
  silêncio por muito tempo.

## Licença

MIT. Veja o arquivo [LICENSE](LICENSE) para o texto completo.
