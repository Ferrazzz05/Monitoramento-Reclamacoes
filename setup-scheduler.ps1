# Cria a tarefa agendada do Reclame Aqui Bot no Agendador de Tarefas do Windows.
#
# A tarefa dispara de hora em hora, das 7h as 17h (o proprio bot pula domingos
# e execucoes fora desse intervalo). Execute este script como Administrador.

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$RunScript  = Join-Path $ProjectDir "run.bat"
$TaskName   = "ReclameAquiBot"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Agendamento do Reclame Aqui Bot"                            -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $RunScript)) {
    Write-Host "ERRO: run.bat nao encontrado em $RunScript" -ForegroundColor Red
    exit 1
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "A tarefa '$TaskName' ja existe. Removendo para recriar..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Write-Host "Criando a tarefa '$TaskName'..." -ForegroundColor Yellow

$action = New-ScheduledTaskAction `
    -Execute $RunScript `
    -WorkingDirectory $ProjectDir

$triggers = @()
foreach ($hour in 7..17) {
    $time = (Get-Date).Date.AddHours($hour)
    $trigger = New-ScheduledTaskTrigger -Daily -At $time
    $trigger.DaysInterval = 1
    $triggers += $trigger
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Principal $principal `
    -Description "Monitora reclamacoes sem resposta no Reclame Aqui." | Out-Null

Write-Host ""
Write-Host "Tarefa criada com sucesso." -ForegroundColor Green
Write-Host ""
Write-Host "Configuracao:"                                           -ForegroundColor White
Write-Host "  Nome:      $TaskName"
Write-Host "  Executavel: $RunScript"
Write-Host "  Horarios:  7h, 8h, 9h ... 17h (todos os dias)"
Write-Host "  Usuario:   $env:USERDOMAIN\$env:USERNAME"
Write-Host ""
Write-Host "O proprio bot ignora execucoes aos domingos."             -ForegroundColor Gray
Write-Host ""
Write-Host "Comandos uteis:"                                          -ForegroundColor White
Write-Host "  Disparar agora:   Start-ScheduledTask -TaskName '$TaskName'"               -ForegroundColor Cyan
Write-Host "  Ver o status:     Get-ScheduledTaskInfo -TaskName '$TaskName'"             -ForegroundColor Cyan
Write-Host "  Remover:          Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Cyan
Write-Host ""
