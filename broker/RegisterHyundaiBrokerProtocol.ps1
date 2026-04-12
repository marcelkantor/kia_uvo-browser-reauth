param(
    [string]$PythonCommand = "py"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$handlerScript = Join-Path $scriptDir "hyundai_broker_protocol.py"

if (-not (Test-Path $handlerScript)) {
    throw "Handler script not found: $handlerScript"
}

$baseKey = "HKCU:\Software\Classes\hyundai-broker"
$commandKey = Join-Path $baseKey "shell\open\command"
$commandValue = '"' + $PythonCommand + '" "' + $handlerScript + '" "%1"'

New-Item -Path $baseKey -Force | Out-Null
Set-Item -Path $baseKey -Value "URL:Hyundai Broker Protocol"
New-ItemProperty -Path $baseKey -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null

New-Item -Path (Join-Path $baseKey "DefaultIcon") -Force | Out-Null
Set-Item -Path (Join-Path $baseKey "DefaultIcon") -Value "$PythonCommand,0"

New-Item -Path $commandKey -Force | Out-Null
Set-Item -Path $commandKey -Value $commandValue

Write-Host "Registered hyundai-broker:// protocol for current user."
Write-Host "Command: $commandValue"
