[CmdletBinding()]
param(
    [string]$OdooRoot = "C:\Program Files\Odoo 18.0e.20260407",
    [string]$Database = "Salarisverwerking-Module",
    [string]$Login = "stagiaire2.rpbg@gmail.com",
    [string]$TemporaryPassword = "Welkom1234",
    [switch]$OpenBrowser,
    [switch]$OpenInPrivate,
    [switch]$DryRun,
    [string]$Remote = "origin",
    [string]$Branch = "staging"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"


function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}


$scriptDir = Split-Path -Parent $PSCommandPath
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$fixScript = Join-Path $scriptDir 'fix_local_login.ps1'

if (-not (Test-Path -LiteralPath $fixScript)) {
    throw "Could not find the login repair script at $fixScript."
}

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.git'))) {
    throw "Could not find the Git repository at $repoRoot."
}

$gitCommand = Get-Command git.exe -ErrorAction SilentlyContinue
if (-not $gitCommand) {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
}

if (-not $gitCommand) {
    throw "Could not find git in PATH. Install Git first or use the local fix_local_login.ps1 directly."
}

$gitPath = if ($gitCommand.Source) { $gitCommand.Source } else { $gitCommand.Path }

Write-Step "Pulling latest changes from $Remote/$Branch"
Push-Location $repoRoot
try {
    & $gitPath fetch $Remote $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "git fetch $Remote $Branch failed with exit code $LASTEXITCODE."
    }

    & $gitPath pull --ff-only $Remote $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "git pull --ff-only $Remote $Branch failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$fixScriptArgs = @{
    OdooRoot = $OdooRoot
    Database = $Database
    Login = $Login
    TemporaryPassword = $TemporaryPassword
}

if ($DryRun) {
    $fixScriptArgs.DryRun = $true
}

if ($OpenBrowser) {
    $fixScriptArgs.OpenBrowser = $true
}
elseif ($OpenInPrivate) {
    $fixScriptArgs.OpenInPrivate = $true
}
else {
    $fixScriptArgs.OpenInPrivate = $true
}

Write-Step "Running local login repair"
& $fixScript @fixScriptArgs