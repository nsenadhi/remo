param(
    [string]$Message = "Auto-sync recovery snapshot"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

git rev-parse --is-inside-work-tree | Out-Null

$status = git status --porcelain
if (-not $status) {
    Write-Host "No changes to sync."
    exit 0
}

git add .
git commit -m $Message
git push origin main

Write-Host "Recovery sync complete."
