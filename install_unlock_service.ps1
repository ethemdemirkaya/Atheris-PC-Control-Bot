# Atheris Unlock Service kurulum scripti.
# Yonetici olarak calistir.
#
# Yaptiklari:
#   1. NSSM yoksa indir (resmi kaynaktan).
#   2. AtherisUnlock servisini LocalSystem hesabiyla kur.
#   3. Servisi otomatik baslat olarak isaretle ve simdi baslat.
#
# Kaldirma:
#   .\install_unlock_service.ps1 -Uninstall

param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ServiceName = "AtherisUnlock"
$ProjectDir = $PSScriptRoot
$ScriptPath = Join-Path $ProjectDir "unlock_service.py"
$NssmDir = Join-Path $ProjectDir "tools\nssm"
$NssmExe = Join-Path $NssmDir "win64\nssm.exe"

function Test-Admin {
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object System.Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Admin)) {
    Write-Error "Yonetici olarak calistirman gerek. PowerShell'i 'Run as Administrator' ile ac."
    exit 1
}

if ($Uninstall) {
    Write-Host "Servis kaldiriliyor..."
    if (Test-Path $NssmExe) {
        & $NssmExe stop $ServiceName 2>$null
        & $NssmExe remove $ServiceName confirm 2>$null
    } else {
        sc.exe stop $ServiceName 2>$null
        sc.exe delete $ServiceName 2>$null
    }
    Write-Host "Tamamlandi."
    exit 0
}

# Python'u bul
$python = $null
foreach ($cand in @("python.exe", "py.exe")) {
    $found = Get-Command $cand -ErrorAction SilentlyContinue
    if ($found) { $python = $found.Source; break }
}
if (-not $python) {
    Write-Error "python.exe PATH'te yok. Python kurulu degil mi?"
    exit 1
}
Write-Host "Python: $python"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "unlock_service.py bulunamadi: $ScriptPath"
    exit 1
}

# NSSM indir
if (-not (Test-Path $NssmExe)) {
    Write-Host "NSSM bulunamadi, indiriliyor..."
    $zipUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $zipPath = Join-Path $env:TEMP "nssm.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    if (-not (Test-Path $NssmDir)) { New-Item -ItemType Directory -Path $NssmDir | Out-Null }
    $tmpExtract = Join-Path $env:TEMP "nssm_extract"
    if (Test-Path $tmpExtract) { Remove-Item $tmpExtract -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $tmpExtract -Force
    $extracted = Get-ChildItem $tmpExtract -Directory | Select-Object -First 1
    Copy-Item -Path (Join-Path $extracted.FullName "win64") -Destination $NssmDir -Recurse -Force
    Remove-Item $zipPath -Force
    Remove-Item $tmpExtract -Recurse -Force
    Write-Host "NSSM indirildi: $NssmExe"
}

# Onceki kurulum varsa kaldir
& $NssmExe stop $ServiceName 2>$null | Out-Null
& $NssmExe remove $ServiceName confirm 2>$null | Out-Null

Write-Host "Servis kuruluyor..."
& $NssmExe install $ServiceName $python $ScriptPath
& $NssmExe set $ServiceName AppDirectory $ProjectDir
& $NssmExe set $ServiceName ObjectName "LocalSystem"
& $NssmExe set $ServiceName Start SERVICE_AUTO_START
& $NssmExe set $ServiceName AppStdout (Join-Path $ProjectDir "logs\unlock_service.stdout.log")
& $NssmExe set $ServiceName AppStderr (Join-Path $ProjectDir "logs\unlock_service.stderr.log")
& $NssmExe set $ServiceName Description "Atheris bot unlock helper (Winlogon desktop input injection)"

Write-Host "Servis baslatiliyor..."
& $NssmExe start $ServiceName

Start-Sleep -Seconds 2
& $NssmExe status $ServiceName

Write-Host ""
Write-Host "Bitti. .env dosyasinda UNLOCK_PASSWORD ve UNLOCK_SERVICE_SECRET dolu olmali."
Write-Host "Ayni UNLOCK_SERVICE_SECRET hem botta hem servisin .env'inde gerekli (ayni dosya zaten)."
