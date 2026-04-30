<#
.SYNOPSIS
    Draai de l10n_sr_hr_payroll testsuite en toon een samenvatting.

.DESCRIPTION
    1. Stopt de Odoo Windows-service (zodat de database vrij is).
    2. Voert de Odoo-testsuite uit via de CLI met --test-enable.
    3. Toont een pass/fail samenvatting in de console.
    4. Slaat het volledige logbestand op op het bureaublad.
    5. Herstart de Odoo Windows-service.

    Vereisten:
    - Uitvoeren als Administrator.
    - De database moet al bestaan en de module moet geinstalleerd zijn.

.PARAMETER OdooRoot
    Pad naar de Odoo-installatie. Standaard: C:\Program Files\Odoo 18.0e.20260407

.PARAMETER Database
    Naam van de Odoo-testdatabase. Standaard: Salarisverwerking-Module

.PARAMETER ModuleName
    Module waarvan de tests worden gedraaid. Standaard: l10n_sr_hr_payroll

.PARAMETER LogDir
    Map waar het testlogbestand wordt opgeslagen. Standaard: bureaublad van de huidige gebruiker.

.PARAMETER SkipServiceRestart
    Schakelaar: herstart Odoo NIET na de test (handig bij meerdere testruns achter elkaar).

.EXAMPLE
    .\run_tests.ps1
    .\run_tests.ps1 -SkipServiceRestart
    .\run_tests.ps1 -Database MijnTestDB -LogDir C:\Logs
#>

[CmdletBinding()]
param(
    [string]$OdooRoot          = 'C:\Program Files\Odoo 18.0e.20260407',
    [string]$Database          = 'Salarisverwerking-Module',
    [string]$ModuleName        = 'l10n_sr_hr_payroll',
    [string]$LogDir            = '',
    [switch]$SkipServiceRestart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-OK   { param([string]$m); Write-Host "    [OK]   $m" -ForegroundColor Green }
function Write-Warn { param([string]$m); Write-Host "    [!]    $m" -ForegroundColor Yellow }
function Write-Fail { param([string]$m); Write-Host "    [FAIL] $m" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Admin-check
# ---------------------------------------------------------------------------

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Fail 'Voer dit script uit als Administrator (rechtsklik -> Als administrator uitvoeren).'
    exit 1
}

# ---------------------------------------------------------------------------
# Paden
# ---------------------------------------------------------------------------

$resolvedRoot = $OdooRoot.TrimEnd('\')
$pythonExe    = Join-Path $resolvedRoot 'python\python.exe'
$odooBin      = Join-Path $resolvedRoot 'server\odoo-bin'
$odooConf     = Join-Path $resolvedRoot 'server\odoo.conf'

$resolvedLogDir = if ($LogDir) {
    $LogDir
} else {
    [Environment]::GetFolderPath('Desktop')
}

$timestamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
$logFile    = Join-Path $resolvedLogDir ("odoo_test_${ModuleName}_${timestamp}.log")

Write-Host ''
Write-Host '====================================================' -ForegroundColor DarkCyan
Write-Host '  SR Payroll -- Testsuite                          ' -ForegroundColor DarkCyan
Write-Host '====================================================' -ForegroundColor DarkCyan
Write-Host ''
Write-Host "  Module   : $ModuleName"
Write-Host "  Database : $Database"
Write-Host "  Logfile  : $logFile"
Write-Host ''

# ---------------------------------------------------------------------------
# Paden valideren
# ---------------------------------------------------------------------------

foreach ($check in @($pythonExe, $odooBin, $odooConf)) {
    if (-not (Test-Path $check)) {
        Write-Fail "Bestand niet gevonden: $check"
        Write-Host '  Controleer de -OdooRoot parameter.' -ForegroundColor Yellow
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Stap 1: Odoo service vinden en stoppen
# ---------------------------------------------------------------------------

Write-Step 'Stap 1/4 -- Odoo Windows-service stoppen'

$odooService = Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '*odoo*' -or $_.DisplayName -like '*odoo*' } |
    Sort-Object Name |
    Select-Object -First 1

if (-not $odooService) {
    Write-Fail 'Geen Odoo Windows-service gevonden. Controleer services.msc.'
    exit 1
}

Write-OK ("Service gevonden: '" + $odooService.Name + "' (status: " + $odooService.Status + ")")

if ($odooService.Status -eq 'Running') {
    Write-Host '    Service stoppen...' -ForegroundColor DarkGray
    Stop-Service -Name $odooService.Name -Force
    $odooService.WaitForStatus('Stopped', [TimeSpan]::FromMinutes(2))
    Write-OK 'Service gestopt.'
} else {
    Write-Warn ('Service was al gestopt (status: ' + $odooService.Status + ').')
}

# ---------------------------------------------------------------------------
# Stap 2: Tests uitvoeren
# ---------------------------------------------------------------------------

Write-Step 'Stap 2/4 -- Tests uitvoeren (dit kan 2-5 minuten duren)'
Write-Host '    Odoo start nu in testmodus. Even geduld...' -ForegroundColor DarkGray
Write-Host ''

$testArgs = @(
    $odooBin,
    '--config',       $odooConf,
    '--database',     $Database,
    '--update',       $ModuleName,
    '--test-enable',
    '--test-tags',    "/$ModuleName",
    '--stop-after-init',
    '--log-level',    'test',
    '--logfile',      $logFile
)

$startTime = Get-Date
& $pythonExe @testArgs
$exitCode  = $LASTEXITCODE
$duration  = [int]((Get-Date) - $startTime).TotalSeconds

Write-Host ''
Write-Host "    Testproces afgesloten na $duration seconden (exit-code: $exitCode)." -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# Stap 3: Logbestand analyseren
# ---------------------------------------------------------------------------

Write-Step 'Stap 3/4 -- Testresultaten analyseren'

if (-not (Test-Path $logFile)) {
    Write-Fail 'Logbestand niet gevonden. De tests zijn mogelijk niet gestart.'
    Write-Host "    Verwacht op: $logFile" -ForegroundColor Yellow
} else {
    $logLines = Get-Content $logFile -ErrorAction SilentlyContinue

    # Zoek de module-testsamenvatting regel
    $summaryLines = $logLines | Where-Object {
        $_ -match 'Module.*test' -or
        $_ -match '\d+ test(s?).*fail' -or
        $_ -match 'FAIL:' -or
        $_ -match 'ERROR:.*test' -or
        $_ -match 'Ran \d+ test'
    }

    # Tel pass/fail uit de Odoo test output
    $failLines  = @($logLines | Where-Object { $_ -match 'FAIL:|AssertionError|ERROR.*test_' })
    $errorLines = @($logLines | Where-Object { $_ -match ' ERROR ' -and $_ -notmatch 'test_enable' })
    $okLines    = @($logLines | Where-Object { $_ -match 'ok$|\.\.\.ok' })

    # Zoek de Odoo-samenvatting: "Module l10n_sr_hr_payroll: X tests, Y failed"
    $moduleLines = @($logLines | Where-Object { $_ -match $ModuleName -and $_ -match 'test' })

    Write-Host ''
    Write-Host '  --- Test Samenvatting ---' -ForegroundColor White

    if ($summaryLines) {
        foreach ($line in $summaryLines | Select-Object -Last 10) {
            $trimmed = $line -replace '^.*\d{4}-\d{2}-\d{2}.*?(ERROR|INFO|WARNING|DEBUG)\s+', ''
            Write-Host "    $trimmed" -ForegroundColor White
        }
    }

    Write-Host ''

    if ($failLines.Count -eq 0 -and $errorLines.Count -eq 0) {
        Write-OK "Geen FAIL of ERROR gevonden in het logbestand."
        Write-OK "Alle gedetecteerde tests zijn geslaagd."
    } else {
        if ($failLines.Count -gt 0) {
            Write-Fail ("$($failLines.Count) FAIL-regels gevonden:")
            foreach ($line in $failLines | Select-Object -First 10) {
                $trimmed = $line -replace '^.*?(FAIL:|ERROR:)', '$1'
                Write-Host "      $trimmed" -ForegroundColor Red
            }
        }
        if ($errorLines.Count -gt 0) {
            Write-Fail ("$($errorLines.Count) ERROR-regels gevonden (eerste 5):")
            foreach ($line in $errorLines | Select-Object -First 5) {
                Write-Host "      $line" -ForegroundColor Red
            }
        }
    }

    Write-Host ''
    Write-Host "  Volledig logbestand: $logFile" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Stap 4: Odoo service herstarten
# ---------------------------------------------------------------------------

if ($SkipServiceRestart) {
    Write-Step 'Stap 4/4 -- Service herstart overgeslagen (-SkipServiceRestart)'
    Write-Warn 'Odoo draait NIET. Start de service handmatig via services.msc als je wilt testen.'
} else {
    Write-Step ("Stap 4/4 -- Odoo-service herstarten ('" + $odooService.Name + "')")
    Write-Host '    Service starten...' -ForegroundColor DarkGray
    Start-Service -Name $odooService.Name
    $odooService.WaitForStatus('Running', [TimeSpan]::FromMinutes(3))
    Write-OK 'Odoo draait weer.'
}

# ---------------------------------------------------------------------------
# Eindstatus
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '====================================================' -ForegroundColor $(if ($exitCode -eq 0) { 'Green' } else { 'Red' })
if ($exitCode -eq 0) {
    Write-Host '  Tests voltooid -- geen fatale fouten gevonden    ' -ForegroundColor Green
} else {
    Write-Host '  Tests voltooid -- er zijn fouten (zie logbestand)' -ForegroundColor Red
}
Write-Host '====================================================' -ForegroundColor $(if ($exitCode -eq 0) { 'Green' } else { 'Red' })
Write-Host ''
Write-Host "  Odoo       : http://172.27.131.3:8069/odoo/payroll" -ForegroundColor White
Write-Host "  Logbestand : $logFile" -ForegroundColor White
Write-Host ''

exit $exitCode
