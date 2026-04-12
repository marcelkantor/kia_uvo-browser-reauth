$baseKey = "HKCU:\Software\Classes\hyundai-broker"

if (Test-Path $baseKey) {
    Remove-Item -Path $baseKey -Recurse -Force
    Write-Host "Removed hyundai-broker:// protocol registration for current user."
} else {
    Write-Host "hyundai-broker:// protocol is not registered for current user."
}
