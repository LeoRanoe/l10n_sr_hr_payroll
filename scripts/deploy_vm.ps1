#Requires -Version 5.1
<#
.SYNOPSIS
    Deploys l10n_sr_hr_payroll database migrations and module upgrade on Windows.

.DESCRIPTION
    Run this after pulling l10n_sr_hr_payroll changes that include database schema changes.
    It will:
      1. Add any missing DB columns via SQL (safe to re-run, uses IF NOT EXISTS).
      2. Upgrade the Odoo module so new fields/data are synced.

.PARAMETER DbName
    Name of the PostgreSQL database to migrate. Defaults to "Salarisverwerking-Module".

.PARAMETER DbUser
    PostgreSQL user. Defaults to "openpg".

.PARAMETER DbPassword
    PostgreSQL password. Defaults to "openpgpwd".

.PARAMETER DbHost
    PostgreSQL host. Defaults to "localhost".

.PARAMETER DbPort
    PostgreSQL port. Defaults to 5432.

.PARAMETER SkipUpgrade
    Skip the Odoo module upgrade step (only run SQL migration).

.PARAMETER SkipSql
    Skip the SQL migration step (only run Odoo module upgrade).

.EXAMPLE
    .\deploy_vm.ps1
    .\deploy_vm.ps1 -DbName "MyOdooDb"
    .\deploy_vm.ps1 -SkipUpgrade
#>

param(
    [string]$DbName     = "Salarisverwerking-Module",
    [string]$DbUser     = "openpg",
    [string]$DbPassword = "openpgpwd",
    [string]$DbHost     = "localhost",
    [int]   $DbPort     = 5432,
    [switch]$SkipUpgrade,
    [switch]$SkipSql
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Paths ────────────────────────────────────────────────────────────────────
$OdooBase   = "C:\Program Files\Odoo 18.0e.20260407"
$PsqlExe    = "$OdooBase\PostgreSQL\bin\psql.exe"
$PythonExe  = "$OdooBase\python\python.exe"
$OdooBin    = "$OdooBase\server\odoo-bin"
$OdooConf   = "$OdooBase\server\odoo.conf"
$SqlScript  = "$PSScriptRoot\migrate_res_company_exchange_rates.sql"

# ─── Helpers ──────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "=== $msg ===" -ForegroundColor Cyan
}

function Assert-File([string]$path, [string]$label) {
    if (-not (Test-Path $path)) {
        Write-Host "ERROR: $label not found at: $path" -ForegroundColor Red
        exit 1
    }
}

# ─── Pre-flight checks ────────────────────────────────────────────────────────
Write-Step "Pre-flight checks"
Assert-File $PsqlExe   "psql.exe"
Assert-File $PythonExe "python.exe"
Assert-File $OdooBin   "odoo-bin"
Assert-File $OdooConf  "odoo.conf"
Assert-File $SqlScript "SQL migration script"
Write-Host "All paths OK." -ForegroundColor Green

# ─── Step 1: SQL migration ────────────────────────────────────────────────────
if (-not $SkipSql) {
    Write-Step "Running SQL migration on database: $DbName"

    $env:PGPASSWORD = $DbPassword

    & $PsqlExe `
        -h $DbHost `
        -p $DbPort `
        -U $DbUser `
        -d $DbName `
        -f $SqlScript

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: psql exited with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "SQL migration complete." -ForegroundColor Green
} else {
    Write-Host "Skipping SQL migration (-SkipSql)." -ForegroundColor Yellow
}

# ─── Step 2: Odoo module upgrade ──────────────────────────────────────────────
if (-not $SkipUpgrade) {
    Write-Step "Upgrading Odoo module: l10n_sr_hr_payroll (database: $DbName)"
    Write-Host "This may take a minute — Odoo will stop after init." -ForegroundColor Gray

    & $PythonExe $OdooBin `
        -c $OdooConf `
        -d $DbName `
        -u l10n_sr_hr_payroll `
        --stop-after-init

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Odoo upgrade exited with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "Module upgrade complete." -ForegroundColor Green
} else {
    Write-Host "Skipping Odoo module upgrade (-SkipUpgrade)." -ForegroundColor Yellow
}

# ─── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Deploy done. Restart Odoo if it is running. ===" -ForegroundColor Green
Write-Host "  Database : $DbName"
Write-Host "  SQL      : $(if ($SkipSql) { 'skipped' } else { 'applied' })"
Write-Host "  Upgrade  : $(if ($SkipUpgrade) { 'skipped' } else { 'applied' })"
