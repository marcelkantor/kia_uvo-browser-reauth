param(
    [string]$HaConfigPath = "Z:\",
    [string]$BrokerInstallPath = "C:\tools\hyundai-broker",
    [switch]$SkipIntegration,
    [switch]$SkipBroker,
    [switch]$SkipProtocolRegistration
)

$ErrorActionPreference = "Stop"

function Copy-DirectoryClean {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (Test-Path $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -Path (Join-Path $Source '*') -Destination $Destination -Recurse -Force
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$integrationSource = Join-Path $scriptDir 'custom_components\kia_uvo'
$brokerSource = Join-Path $scriptDir 'broker'

if (-not (Test-Path $integrationSource)) {
    throw "Integration source not found: $integrationSource"
}

if (-not $SkipIntegration) {
    $targetCustomComponents = Join-Path $HaConfigPath 'custom_components'
    $targetIntegration = Join-Path $targetCustomComponents 'kia_uvo'
    $backupRoot = Join-Path $HaConfigPath 'backups\custom_components'
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'

    New-Item -ItemType Directory -Path $targetCustomComponents -Force | Out-Null
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

    if (Test-Path $targetIntegration) {
        $backupTarget = Join-Path $backupRoot "kia_uvo_preinstall_$timestamp"
        Copy-Item -Path $targetIntegration -Destination $backupTarget -Recurse -Force
        Write-Host "Backup existing integration -> $backupTarget"
    }

    Copy-DirectoryClean -Source $integrationSource -Destination $targetIntegration
    Write-Host "Installed integration -> $targetIntegration"
}

if (-not $SkipBroker) {
    if (-not (Test-Path $brokerSource)) {
        throw "Broker source not found: $brokerSource"
    }

    New-Item -ItemType Directory -Path $BrokerInstallPath -Force | Out-Null
    Copy-Item -Path (Join-Path $brokerSource '*') -Destination $BrokerInstallPath -Recurse -Force
    Write-Host "Installed broker -> $BrokerInstallPath"

    if (-not $SkipProtocolRegistration) {
        $registerScript = Join-Path $BrokerInstallPath 'RegisterHyundaiBrokerProtocol.ps1'
        powershell -ExecutionPolicy Bypass -File $registerScript
    }
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Restart Home Assistant Core."
Write-Host "2. In HA, open the integration and run Re-authenticate."
Write-Host "3. Use the Open website button or the fallback command if needed."
