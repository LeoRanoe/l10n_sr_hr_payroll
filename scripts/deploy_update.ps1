<#
.SYNOPSIS
    Pull de laatste wijzigingen van staging en herstart Odoo.

.DESCRIPTION
    1. Trekt de nieuwste code van de staging-branch van GitHub.
    2. Stopt de Odoo Windows-service.
    3. Herstart de Odoo Windows-service (en voert optioneel een module-upgrade uit).

    Vereisten op de VM:
    - Git staat in het PATH (wordt geleverd door de bootstrap).
    - De Odoo Windows-service draait.
    - Het script wordt uitgevoerd als Administrator (nodig voor service-beheer).

.PARAMETER OdooRoot
    Map met de Odoo-installatie. Standaard: C:\Program Files\Odoo 18.0e.20260407

.PARAMETER AddonsRoot
    Map met de custom addons. Standaard: <OdooRoot>\sessions\addons\18.0

.PARAMETER ModuleName
    Naam van de module die bijgewerkt wordt. Standaard: l10n_sr_hr_payroll

.PARAMETER Database
    Naam van de Odoo-database. Standaard: Salarisverwerking-Module

.PARAMETER Branch
    Git-branch om van te pullen. Standaard: staging

.PARAMETER Remote
    Git-remote. Standaard: origin

.PARAMETER UpgradeModule
    Schakelaar: voer ook -u <module> uit (nodig bij modelwijzigingen).

.PARAMETER DryRun
    Schakelaar: toon wat er gedaan zou worden zonder iets uit te voeren.

.EXAMPLE
    # Gewone update (alleen code, geen DB-migratie)
    .\deploy_update.ps1

    # Update inclusief module-upgrade (bij nieuwe velden of views)
    .\deploy_update.ps1 -UpgradeModule

    # Droog draaien om te zien wat het script zou doen
    .\deploy_update.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [string]$OdooRoot     = 'C:\Program Files\Odoo 18.0e.20260407',
    [string]$AddonsRoot   = '',
    [string]$ModuleName   = 'l10n_sr_hr_payroll',
    [string]$Database     = 'Salarisverwerking-Module',
    [string]$Branch       = 'staging',
    [string]$Remote       = 'origin',
    [switch]$UpgradeModule,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ─── Helpers ──────────────────────────────────────────────────────────────────

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$Message)
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    [!]  $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "    [FAIL] $Message" -ForegroundColor Red
}

function Invoke-Step {
    param(
        [string]$Description,
        [scriptblock]$Action
    )
    if ($DryRun) {
        Write-Host "  [dry-run] $Description" -ForegroundColor DarkGray
        return
    }
    & $Action
}

# ─── Administrator-check ──────────────────────────────────────────────────────

$currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Fail 'Dit script moet als Administrator worden uitgevoerd.'
    Write-Host '  Klik rechts op deploy_update.cmd en kies "Als administrator uitvoeren".' -ForegroundColor Yellow
    exit 1
}

# ─── Paden oplossen ───────────────────────────────────────────────────────────

$resolvedOdooRoot  = $OdooRoot.TrimEnd('\')
$resolvedAddonsRoot = if ($AddonsRoot) {
    $AddonsRoot.TrimEnd('\')
} else {
    Join-Path $resolvedOdooRoot 'sessions\addons\18.0'
}

$moduleDir  = Join-Path $resolvedAddonsRoot $ModuleName
$pythonExe  = Join-Path $resolvedOdooRoot 'python\python.exe'
$odooBin    = Join-Path $resolvedOdooRoot 'server\odoo-bin'
$odooConf   = Join-Path $resolvedOdooRoot 'server\odoo.conf'

Write-Host ''
Write-Host '╔══════════════════════════════════════════════════════╗' -ForegroundColor DarkCyan
Write-Host '║   SR Payroll — Deploy & Update script                ║' -ForegroundColor DarkCyan
Write-Host '╚══════════════════════════════════════════════════════╝' -ForegroundColor DarkCyan
Write-Host ''
Write-Host "  Module    : $ModuleName"
Write-Host "  Branch    : $Remote/$Branch"
Write-Host "  Repo map  : $moduleDir"
Write-Host "  Database  : $Database"
if ($UpgradeModule) { Write-Warn 'Module-upgrade ingeschakeld (-u). Dit duurt langer.' }
if ($DryRun)        { Write-Warn 'DRY-RUN modus — er wordt niets daadwerkelijk uitgevoerd.' }
Write-Host ''

# ─── Stap 1: Git pull ─────────────────────────────────────────────────────────

Write-Step "Stap 1/4 — Nieuwste code ophalen van $Remote/$Branch"

if (-not (Test-Path (Join-Path $moduleDir '.git'))) {
    Write-Fail "Geen git-repository gevonden in: $moduleDir"
    Write-Host "  Zorg dat de module al is gekloned via bootstrap_test_vm.ps1" -ForegroundColor Yellow
    exit 1
}

$gitExe = (Get-Command git -ErrorAction SilentlyContinue)?.Source
if (-not $gitExe) {
    Write-Fail 'Git niet gevonden in het PATH. Installeer Git for Windows.'
    exit 1
}

Push-Location $moduleDir
try {
    Invoke-Step "git fetch $Remote" {
        & git fetch $Remote 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "git fetch mislukt (exit $LASTEXITCODE)." }
    }

    Invoke-Step "git checkout $Branch && git reset --hard $Remote/$Branch" {
        & git checkout $Branch 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "git checkout $Branch mislukt." }

        & git reset --hard "$Remote/$Branch" 2>&1 | ForEach-Object { Write-Host "    $_" }
        if ($LASTEXITCODE -ne 0) { throw "git reset --hard mislukt." }
    }

    if (-not $DryRun) {
        $commitHash = (& git rev-parse --short HEAD 2>$null).Trim()
        Write-OK "Code bijgewerkt naar commit: $commitHash"
    }
}
finally {
    Pop-Location
}

# ─── Stap 2: Odoo service opzoeken ────────────────────────────────────────────

Write-Step 'Stap 2/4 — Odoo Windows-service opsporen'

$odooService = Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '*odoo*' -or $_.DisplayName -like '*odoo*' } |
    Sort-Object Name |
    Select-Object -First 1

if (-not $odooService) {
    Write-Fail 'Geen Odoo Windows-service gevonden.'
    Write-Host "  Controleer of Odoo is geïnstalleerd als Windows-service (services.msc)." -ForegroundColor Yellow
    exit 1
}

Write-OK "Service gevonden: '$($odooService.Name)' (status: $($odooService.Status))"

# ─── Stap 3: Service herstarten ───────────────────────────────────────────────

Write-Step "Stap 3/4 — Odoo-service herstarten ('$($odooService.Name)')"

Invoke-Step "Stop-Service '$($odooService.Name)'" {
    if ($odooService.Status -eq 'Running') {
        Write-Host "    Service stoppen..." -ForegroundColor DarkGray
        Stop-Service -Name $odooService.Name -Force
        $odooService.WaitForStatus('Stopped', [TimeSpan]::FromMinutes(2))
        Write-OK 'Service gestopt.'
    } else {
        Write-Warn "Service was al gestopt (status: $($odooService.Status))."
    }
}

# ─── Stap 4a (optioneel): Module-upgrade ──────────────────────────────────────

if ($UpgradeModule) {
    Write-Step "Stap 4/4 — Module '$ModuleName' upgraden in database '$Database'"

    if (-not (Test-Path $pythonExe)) {
        Write-Fail "Python niet gevonden op: $pythonExe"
        exit 1
    }
    if (-not (Test-Path $odooBin)) {
        Write-Fail "Odoo-bin niet gevonden op: $odooBin"
        exit 1
    }

    $upgradeArgs = @(
        $odooBin,
        '--config', $odooConf,
        '--database', $Database,
        '--update', $ModuleName,
        '--stop-after-init',
        '--no-http'
    )

    Invoke-Step "python odoo-bin -u $ModuleName --stop-after-init" {
        Write-Host "    Dit kan 30-120 seconden duren..." -ForegroundColor DarkGray
        & $pythonExe @upgradeArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Module-upgrade mislukt (exit $LASTEXITCODE). Check de Odoo-logs."
            exit 1
        }
        Write-OK "Module '$ModuleName' succesvol geüpgraded."
    }
} else {
    Write-Step 'Stap 4/4 — Odoo-service starten (geen module-upgrade)'
    Write-Warn 'Gebruik -UpgradeModule als er nieuwe velden of views zijn toegevoegd.'
}

# ─── Service starten ──────────────────────────────────────────────────────────

Invoke-Step "Start-Service '$($odooService.Name)'" {
    Write-Host "    Service starten..." -ForegroundColor DarkGray
    Start-Service -Name $odooService.Name
    $odooService.WaitForStatus('Running', [TimeSpan]::FromMinutes(3))
    Write-OK "Service gestart. Odoo draait weer op poort 8069."
}

# ─── Klaar ────────────────────────────────────────────────────────────────────

Write-Host ''
Write-Host '╔══════════════════════════════════════════════════════╗' -ForegroundColor Green
Write-Host '║   Deploy voltooid!                                   ║' -ForegroundColor Green
Write-Host '╚══════════════════════════════════════════════════════╝' -ForegroundColor Green
Write-Host ''
Write-Host "  Open Odoo: http://localhost:8069" -ForegroundColor White
Write-Host "  Help-pagina: http://localhost:8069/sr_payroll/help" -ForegroundColor White
Write-Host ''
