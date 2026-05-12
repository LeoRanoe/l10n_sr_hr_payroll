<#
.SYNOPSIS
    Pull de laatste wijzigingen van staging, synchroniseert de database en herstart Odoo.

.DESCRIPTION
    1. Trekt de nieuwste code van de staging-branch van GitHub.
    2. Stopt de Odoo Windows-service.
    3. Voert automatisch SQL-migraties en een Odoo module-upgrade uit als er
       nieuwe commits zijn opgehaald of als -UpgradeModule is meegegeven.
    4. Herstart de Odoo Windows-service.

    Vereisten op de VM:
    - Git staat in het PATH.
    - De Odoo Windows-service draait.
    - Het script wordt uitgevoerd als Administrator.

.PARAMETER OdooRoot
    Map met de Odoo-installatie. Standaard: C:\Program Files\Odoo 18.0e.20260407

.PARAMETER AddonsRoot
    Map met de custom addons. Standaard: <OdooRoot>\sessions\addons\18.0

.PARAMETER ModuleName
    Naam van de module. Standaard: l10n_sr_hr_payroll

.PARAMETER Database
    Naam van de Odoo-database. Standaard: Salarisverwerking-Module

.PARAMETER Branch
    Git-branch om van te pullen. Standaard: staging

.PARAMETER Remote
    Git-remote. Standaard: origin

.PARAMETER UpgradeModule
    Schakelaar: forceer een database-sync ook als er geen nieuwe commit is.

.PARAMETER SkipUpgradeModule
    Schakelaar: sla de Odoo module-upgrade over, ook als er nieuwe commits zijn.

.PARAMETER SkipSqlMigrations
    Schakelaar: sla losse migrate_*.sql scripts over.

.PARAMETER DryRun
    Schakelaar: toon wat er gedaan zou worden zonder iets uit te voeren.

.EXAMPLE
    .\deploy_update.ps1
    .\deploy_update.ps1 -UpgradeModule
    .\deploy_update.ps1 -SkipUpgradeModule
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
    [switch]$SkipUpgradeModule,
    [switch]$SkipSqlMigrations,
    [switch]$DryRun
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

function Get-OdooConfValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Default = ''
    )

    if (-not (Test-Path $Path)) {
        return $Default
    }

    $pattern = '^\s*' + [regex]::Escape($Key) + '\s*=\s*(.*)\s*$'
    $match = Select-String -Path $Path -Pattern $pattern | Select-Object -First 1
    if (-not $match) {
        return $Default
    }

    $value = $match.Matches[0].Groups[1].Value.Trim()
    if (-not $value -or $value -eq 'False') {
        return $Default
    }

    return $value
}

if ($UpgradeModule -and $SkipUpgradeModule) {
    Write-Fail 'Gebruik -UpgradeModule en -SkipUpgradeModule niet tegelijk.'
    exit 1
}

# ---------------------------------------------------------------------------
# Administrator-check
# ---------------------------------------------------------------------------

$currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Fail 'Dit script moet als Administrator worden uitgevoerd.'
    Write-Host '  Klik rechts op deploy_update.cmd en kies "Als administrator uitvoeren".' -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
# Paden oplossen
# ---------------------------------------------------------------------------

$resolvedOdooRoot = $OdooRoot.TrimEnd('\')
if ($AddonsRoot) {
    $resolvedAddonsRoot = $AddonsRoot.TrimEnd('\')
} else {
    $resolvedAddonsRoot = Join-Path $resolvedOdooRoot 'sessions\addons\18.0'
}

$moduleDir = Join-Path $resolvedAddonsRoot $ModuleName
$pythonExe = Join-Path $resolvedOdooRoot 'python\python.exe'
$odooBin   = Join-Path $resolvedOdooRoot 'server\odoo-bin'
$odooConf  = Join-Path $resolvedOdooRoot 'server\odoo.conf'
$pgPath    = Get-OdooConfValue -Path $odooConf -Key 'pg_path' -Default (Join-Path $resolvedOdooRoot 'PostgreSQL\bin')
$psqlExe   = Join-Path $pgPath 'psql.exe'
$dbHost    = Get-OdooConfValue -Path $odooConf -Key 'db_host' -Default 'localhost'
$dbPort    = Get-OdooConfValue -Path $odooConf -Key 'db_port' -Default '5432'
$dbUser    = Get-OdooConfValue -Path $odooConf -Key 'db_user' -Default 'openpg'
$dbPassword = Get-OdooConfValue -Path $odooConf -Key 'db_password'
$sqlMigrationScripts = @(Get-ChildItem -Path $PSScriptRoot -Filter 'migrate_*.sql' -File -ErrorAction SilentlyContinue | Sort-Object Name)
$previousCommitHash = $null
$newCommitHash = $null
$hasNewCommit = $false
$shouldUpgradeModule = $false
$shouldRunSqlMigrations = $false

Write-Host ''
Write-Host '====================================================' -ForegroundColor DarkCyan
Write-Host '  SR Payroll -- Deploy & Update                    ' -ForegroundColor DarkCyan
Write-Host '====================================================' -ForegroundColor DarkCyan
Write-Host ''
Write-Host "  Module    : $ModuleName"
Write-Host "  Branch    : $Remote/$Branch"
Write-Host "  Repo map  : $moduleDir"
Write-Host "  Database  : $Database"
Write-Host '  DB sync   : automatisch bij nieuwe commits'

if ($UpgradeModule) {
    Write-Warn 'Geforceerde database-sync ingeschakeld (-UpgradeModule). Dit duurt langer.'
}
if ($SkipUpgradeModule) {
    Write-Warn 'Automatische module-upgrade uitgeschakeld (-SkipUpgradeModule).'
}
if ($SkipSqlMigrations) {
    Write-Warn 'Automatische SQL-migraties uitgeschakeld (-SkipSqlMigrations).'
}
if ($DryRun) {
    Write-Warn 'DRY-RUN modus -- er wordt niets daadwerkelijk uitgevoerd.'
}
Write-Host ''

# ---------------------------------------------------------------------------
# Stap 1: Git pull
# ---------------------------------------------------------------------------

Write-Step "Stap 1/6 -- Nieuwste code ophalen van $Remote/$Branch"

if (-not (Test-Path (Join-Path $moduleDir '.git'))) {
    Write-Fail "Geen git-repository gevonden in: $moduleDir"
    Write-Host '  Zorg dat de module al is gekloned via de bootstrap.' -ForegroundColor Yellow
    exit 1
}

$gitCmd = (Get-Command git -ErrorAction SilentlyContinue)
if (-not $gitCmd) {
    Write-Fail 'Git niet gevonden in het PATH. Installeer Git for Windows.'
    exit 1
}
$gitExe = $gitCmd.Source

Push-Location $moduleDir
try {
    if (-not $DryRun) {
        $previousCommitHash = (& $gitExe rev-parse HEAD 2>$null | Select-Object -First 1)
        if ($previousCommitHash) {
            $previousCommitHash = $previousCommitHash.ToString().Trim()
        }
    }

    Invoke-Step "git fetch $Remote" {
        # SilentlyContinue: voorkomt dat PS5.1 git-stderr als exception behandelt
        $prev = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
        $result = & $gitExe fetch $Remote 2>&1
        $exitFetch = $LASTEXITCODE
        $ErrorActionPreference = $prev
        $result | ForEach-Object { Write-Host "    $_" }
        if ($exitFetch -ne 0) { throw "git fetch mislukt (exit $exitFetch)." }
    }

    Invoke-Step "git checkout $Branch" {
        $prev = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
        $result = & $gitExe checkout $Branch 2>&1
        $exitCheckout = $LASTEXITCODE
        $ErrorActionPreference = $prev
        # "Already on '...'" is informatief, geen fout
        $result | Where-Object { $_ -and $_ -notmatch 'Already on' } |
            ForEach-Object { Write-Host "    $_" }
        if ($exitCheckout -ne 0) { throw "git checkout $Branch mislukt (exit $exitCheckout)." }
        Write-OK "Op branch: $Branch"
    }

    Invoke-Step "git reset --hard $Remote/$Branch" {
        $prev = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
        $result = & $gitExe reset --hard "$Remote/$Branch" 2>&1
        $exitReset = $LASTEXITCODE
        $ErrorActionPreference = $prev
        $result | ForEach-Object { Write-Host "    $_" }
        if ($exitReset -ne 0) { throw "git reset --hard mislukt (exit $exitReset)." }
    }

    if (-not $DryRun) {
        $newCommitHash = (& $gitExe rev-parse HEAD 2>$null | Select-Object -First 1)
        if ($newCommitHash) {
            $newCommitHash = $newCommitHash.ToString().Trim()
        }

        $hasNewCommit = $previousCommitHash -ne $newCommitHash
        if ($newCommitHash) {
            $shortCommitHash = (& $gitExe rev-parse --short HEAD 2>$null | Select-Object -First 1)
            if ($shortCommitHash) {
                Write-OK "Code bijgewerkt naar commit: $($shortCommitHash.ToString().Trim())"
            }
        }

        if ($hasNewCommit) {
            Write-OK 'Nieuwe commit gedetecteerd; database-sync wordt automatisch uitgevoerd.'
        } else {
            Write-OK 'Geen nieuwe commit opgehaald; database-sync wordt overgeslagen tenzij geforceerd.'
        }
    }
}
finally {
    Pop-Location
}

if ($DryRun) {
    if ($UpgradeModule) {
        $shouldUpgradeModule = $true
    } else {
        Write-Warn 'Dry-run: automatische database-sync wordt pas na een echte git fetch bepaald.'
    }
} else {
    $shouldUpgradeModule = (-not $SkipUpgradeModule) -and ($UpgradeModule -or $hasNewCommit)
}

$shouldRunSqlMigrations = $shouldUpgradeModule -and (-not $SkipSqlMigrations) -and ($sqlMigrationScripts.Count -gt 0)

# ---------------------------------------------------------------------------
# Stap 2: Odoo service opzoeken
# ---------------------------------------------------------------------------

Write-Step 'Stap 2/6 -- Odoo Windows-service opsporen'

$odooService = Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '*odoo*' -or $_.DisplayName -like '*odoo*' } |
    Sort-Object Name |
    Select-Object -First 1

if (-not $odooService) {
    Write-Fail 'Geen Odoo Windows-service gevonden.'
    Write-Host '  Controleer of Odoo is geinstalleerd als Windows-service (services.msc).' -ForegroundColor Yellow
    exit 1
}

Write-OK ("Service gevonden: '" + $odooService.Name + "' (status: " + $odooService.Status + ")")

# ---------------------------------------------------------------------------
# Stap 3: Service stoppen
# ---------------------------------------------------------------------------

Write-Step ("Stap 3/6 -- Odoo-service stoppen ('" + $odooService.Name + "')")

Invoke-Step ("Stop-Service '" + $odooService.Name + "'") {
    if ($odooService.Status -eq 'Running') {
        Write-Host '    Service stoppen...' -ForegroundColor DarkGray
        Stop-Service -Name $odooService.Name -Force
        $odooService.WaitForStatus('Stopped', [TimeSpan]::FromMinutes(2))
        Write-OK 'Service gestopt.'
    } else {
        Write-Warn ("Service was al gestopt (status: " + $odooService.Status + ").")
    }
}

# ---------------------------------------------------------------------------
# Stap 4: Optionele SQL migraties uitvoeren
# ---------------------------------------------------------------------------

Write-Step 'Stap 4/6 -- SQL migraties toepassen'

if ($shouldRunSqlMigrations) {
    if (-not (Test-Path $psqlExe)) {
        Write-Fail "psql.exe niet gevonden op: $psqlExe"
        exit 1
    }

    $previousPgPassword = $env:PGPASSWORD
    try {
        if ($dbPassword) {
            $env:PGPASSWORD = $dbPassword
        } else {
            Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
        }

        foreach ($sqlScript in $sqlMigrationScripts) {
            Invoke-Step ("psql -f " + $sqlScript.Name) {
                Write-Host ("    SQL migratie: " + $sqlScript.Name) -ForegroundColor DarkGray
                & $psqlExe `
                    -v 'ON_ERROR_STOP=1' `
                    -h $dbHost `
                    -p $dbPort `
                    -U $dbUser `
                    -d $Database `
                    -f $sqlScript.FullName

                if ($LASTEXITCODE -ne 0) {
                    Write-Fail ("SQL migratie mislukt voor '" + $sqlScript.Name + "' (exit " + $LASTEXITCODE + ").")
                    exit 1
                }
            }
        }

        Write-OK ("SQL migraties succesvol toegepast: " + (($sqlMigrationScripts | ForEach-Object Name) -join ', '))
    }
    finally {
        if ($null -ne $previousPgPassword) {
            $env:PGPASSWORD = $previousPgPassword
        } else {
            Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
        }
    }
} elseif ($SkipSqlMigrations) {
    Write-Warn 'SQL migraties overgeslagen (-SkipSqlMigrations).'
} elseif ($sqlMigrationScripts.Count -eq 0) {
    Write-OK 'Geen migrate_*.sql scripts gevonden.'
} else {
    Write-OK 'Geen database-sync nodig; SQL migraties worden overgeslagen.'
}

# ---------------------------------------------------------------------------
# Stap 5: Optionele module-upgrade uitvoeren
# ---------------------------------------------------------------------------

Write-Step ("Stap 5/6 -- Module '" + $ModuleName + "' upgraden in database '" + $Database + "'")

if ($shouldUpgradeModule) {

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

    Invoke-Step ("python odoo-bin -u " + $ModuleName + " --stop-after-init") {
        Write-Host '    Dit kan 30-120 seconden duren...' -ForegroundColor DarkGray
        & $pythonExe @upgradeArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Fail ("Module-upgrade mislukt (exit " + $LASTEXITCODE + "). Check de Odoo-logs.")
            exit 1
        }
        Write-OK ("Module '" + $ModuleName + "' succesvol geupgraded.")
    }
} elseif ($SkipUpgradeModule) {
    Write-Warn 'Module-upgrade overgeslagen (-SkipUpgradeModule).'
} else {
    Write-OK 'Geen nieuwe commit opgehaald; module-upgrade niet nodig.'
}

# ---------------------------------------------------------------------------
# Stap 6: Service starten
# ---------------------------------------------------------------------------

Write-Step ("Stap 6/6 -- Odoo-service starten ('" + $odooService.Name + "')")

Invoke-Step ("Start-Service '" + $odooService.Name + "'") {
    Write-Host '    Service starten...' -ForegroundColor DarkGray
    Start-Service -Name $odooService.Name
    $odooService.WaitForStatus('Running', [TimeSpan]::FromMinutes(3))
    Write-OK 'Service gestart. Odoo draait weer op poort 8069.'
}

# ---------------------------------------------------------------------------
# Klaar
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '====================================================' -ForegroundColor Green
Write-Host '  Deploy voltooid!                                  ' -ForegroundColor Green
Write-Host '====================================================' -ForegroundColor Green
Write-Host ''
Write-Host '  Open Odoo      : http://localhost:8069' -ForegroundColor White
Write-Host '  Help-pagina    : http://localhost:8069/sr_payroll/help' -ForegroundColor White
Write-Host ''
