# backup.ps1 - verified backup of the AI Sales Dashboard project + PostgreSQL DB.
#
# Creates, inside $BackupDir:
#   <name>-<timestamp>.tar            project source archive (excludes .venv, node_modules, .git, .env, backups, cache)
#   <name>-<timestamp>.dump           pg_dump of the live database
#   <name>-<timestamp>-manifest.sha256  SHA256 manifest of every archived file
# and prints a verification report. Exit code 0 on success.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File infra\backup.ps1 [-BackupDir <path>] [-Name baseline]
# Defaults: BackupDir = <project>\backups (gitignored), Name = "backup".
# For the canonical baseline store outside the repo (e.g. %TEMP%\opencode\backups), pass -BackupDir explicitly.

param(
    [string]$BackupDir = "",
    [string]$Name = "backup"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $BackupDir) { $BackupDir = Join-Path $ProjectRoot "backups" }
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Base = "$Name-$Stamp"
$Tar = Join-Path $BackupDir "$Base.tar"
$Dump = Join-Path $BackupDir "$Base.dump"
$Manifest = Join-Path $BackupDir "$Base-manifest.sha256"

Write-Host "Backing up project to: $Tar"
$tarArgs = @(
    "--exclude=backend/.venv", "--exclude=frontend/node_modules", "--exclude=.git",
    "--exclude=.env", "--exclude=backend/.env", "--exclude=backups", "--exclude=__pycache__",
    "--exclude=*.pyc", "--exclude=.next", "--exclude=uvicorn.log", "--exclude=uvicorn-err.log",
    "-cf", $Tar, "-C", $ProjectRoot, "."
)
& "C:\Windows\System32\tar.exe" @tarArgs
if ($LASTEXITCODE -ne 0) { throw "tar failed with exit code $LASTEXITCODE" }

Write-Host "Backing up database to: $Dump"
$env:PGPASSWORD = "dashboard"
$pgDump = "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"
& $pgDump -U dashboard -h localhost -p 5432 -d dashboard -F c -f $Dump
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

Write-Host "Generating SHA256 manifest: $Manifest"
$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP)
$extractDir = Join-Path $tempRoot "opencode-backup-verify-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $extractDir | Out-Null
& "C:\Windows\System32\tar.exe" -xf $Tar -C $extractDir
if ($LASTEXITCODE -ne 0) { throw "tar extract failed with exit code $LASTEXITCODE" }

$manifestLines = @()
Get-ChildItem -LiteralPath $extractDir -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($extractDir.Length + 1).Replace("\", "/")
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
    $manifestLines += "$hash  $rel"
}
Remove-Item -LiteralPath $extractDir -Recurse -Force
$manifestLines | Set-Content -Path $Manifest -Encoding utf8

Write-Host ""
Write-Host "===== BACKUP VERIFICATION ====="
$tarEntryCount = (& tar.exe -tf $Tar).Count
$tarInfo = Get-Item $Tar
$dumpInfo = Get-Item $Dump
$manifestInfo = Get-Item $Manifest
Write-Host ("tar:   {0} entries, {1:N2} MB" -f $tarEntryCount, ($tarInfo.Length / 1MB))
Write-Host ("dump:  {0:N2} MB" -f ($dumpInfo.Length / 1MB))
Write-Host ("sha256 manifest entries: {0}" -f $manifestLines.Count)
Write-Host "Artifacts:"
Write-Host "  $Tar"
Write-Host "  $Dump"
Write-Host "  $Manifest"
Write-Host "===== DONE ====="