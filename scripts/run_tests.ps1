<#
.SYNOPSIS
    Draai de l10n_sr_hr_payroll testsuite en toon een samenvatting.

.DESCRIPTION
    1. Stopt de Odoo Windows-service.
    2. Voert de tests uit via de Odoo CLI en vangt alle output op.
    3. Toont een pass/fail samenvatting in de console.
    4. Slaat het volledige logbestand op op het bureaublad.
    5. Herstart de Odoo Windows-service.

    Vereisten:
    - Uitvoeren als Administrator.
    - De module moet geinstalleerd zijn in de opgegeven database.
    - psql.exe moet bereikbaar zijn (voor de database-check).

.PARAMETER OdooRoot
    Pad naar de Odoo-installatie. Standaard: C:\Program Files\Odoo 18.0e.20260407

.PARAMETER Database
    Naam van de Odoo-testdatabase. Standaard: Salarisverwerking-Module

.PARAMETER ModuleName
    Module waarvan de tests worden gedraaid. Standaard: l10n_sr_hr_payroll

.PARAMETER LogDir
    Map voor het logbestand. Standaard: bureaublad van de huidige gebruiker.

.PARAMETER SkipServiceRestart
    Schakelaar: herstart Odoo NIET na de test.

.EXAMPLE
    .\run_tests.ps1
    .\run_tests.ps1 -SkipServiceRestart
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

function Write-Step { param([string]$m); Write-Host ''; Write-Host "==> $m" -ForegroundColor Cyan }
function Write-OK   { param([string]$m); Write-Host "    [OK]   $m" -ForegroundColor Green }
function Write-Warn { param([string]$m); Write-Host "    [!]    $m" -ForegroundColor Yellow }
function Write-Fail { param([string]$m); Write-Host "    [FAIL] $m" -ForegroundColor Red }

function Invoke-Native {
    param([string]$Exe, [string[]]$Arguments)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $output = & $Exe @Arguments 2>&1
    $code   = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return [PSCustomObject]@{ Output = $output; ExitCode = $code }
}

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
# pg_path staat in odoo.conf; psql.exe zit in die map
$psqlExe      = Join-Path $resolvedRoot 'PostgreSQL\bin\psql.exe'

$resolvedLogDir = if ($LogDir) { $LogDir } else { [Environment]::GetFolderPath('Desktop') }
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
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Stap 1: Controleer of de module in de database staat
# ---------------------------------------------------------------------------

Write-Step 'Stap 1/5 -- Database-check: is de module geinstalleerd?'

# ---------------------------------------------------------------------------
# Lees db_password uit odoo.conf zodat psql niet om een wachtwoord vraagt.
# PGPASSWORD wordt na afloop weer verwijderd.
# ---------------------------------------------------------------------------
$dbPassword  = 'openpgpwd'   # standaard uit odoo.conf
$dbUser      = 'openpg'
$dbHost      = 'localhost'
$dbPort      = '5432'
$odooLogFile = ''

if (Test-Path $odooConf) {
    $confContent = Get-Content $odooConf -Raw
    if ($confContent -match 'db_password\s*=\s*(.+)') {
        $parsed = $Matches[1].Trim()
        if ($parsed -and $parsed -ne 'False') { $dbPassword = $parsed }
    }
    if ($confContent -match 'db_user\s*=\s*(.+)') {
        $parsed = $Matches[1].Trim()
        if ($parsed -and $parsed -ne 'False') { $dbUser = $parsed }
    }
    if ($confContent -match 'db_host\s*=\s*(.+)') {
        $parsed = $Matches[1].Trim()
        if ($parsed -and $parsed -ne 'False' -and $parsed -ne 'localhost') { $dbHost = $parsed }
    }
    if ($confContent -match 'db_port\s*=\s*(.+)') {
        $parsed = $Matches[1].Trim()
        if ($parsed -and $parsed -ne 'False') { $dbPort = $parsed }
    }
    if ($confContent -match 'logfile\s*=\s*(.+)') {
        $parsed = $Matches[1].Trim()
        if ($parsed -and $parsed -ne 'False') { $odooLogFile = $parsed }
    }
}

# Zet PGPASSWORD zodat psql nooit om een wachtwoord vraagt
$env:PGPASSWORD = $dbPassword

function Invoke-Psql {
    param([string]$DbName, [string]$Sql)
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
    $out  = & $psqlExe -U $dbUser -h $dbHost -p $dbPort -d $DbName -t -A -c $Sql 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return [PSCustomObject]@{ Output = $out; ExitCode = $code }
}

$moduleInstalled  = $false
$detectedDatabase = $Database

if (Test-Path $psqlExe) {
    $sql = "SELECT state FROM ir_module_module WHERE name='$ModuleName' LIMIT 1;"

    $res = Invoke-Psql -DbName $Database -Sql $sql
    if ($res.ExitCode -eq 0) {
        $stateValue = ($res.Output -join '').Trim()
        Write-Host "    Module state in '$Database': '$stateValue'"

        if ($stateValue -eq 'installed') {
            $moduleInstalled = $true
            Write-OK "Module is geinstalleerd in '$Database'. Tests kunnen draaien."
        } else {
            Write-Warn "Module staat NIET op 'installed' in '$Database' (staat op: '$stateValue')."
            Write-Host '    Zoeken in welke database de module wel geinstalleerd is...' -ForegroundColor DarkGray

            $listRes = Invoke-Psql -DbName 'postgres' -Sql "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY datname;"
            $foundIn = @()
            foreach ($dbName in ($listRes.Output | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ })) {
                $chk = Invoke-Psql -DbName $dbName -Sql $sql
                if ($chk.ExitCode -eq 0 -and ($chk.Output -join '').Trim() -eq 'installed') {
                    $foundIn += $dbName
                }
            }

            if ($foundIn.Count -gt 0) {
                Write-OK ("Module 'installed' gevonden in: " + ($foundIn -join ', '))
                $detectedDatabase = $foundIn[0]
                Write-Host "    Tests worden gedraaid op: '$detectedDatabase'" -ForegroundColor Yellow
                $moduleInstalled = $true
            } else {
                Write-Fail 'Module is in geen enkele database als installed gevonden.'
                Write-Host '  Installeer de module via http://172.27.131.3:8069/odoo/settings/apps' -ForegroundColor Yellow
                Write-Host '  of voer deploy_update.cmd uit met de -UpgradeModule schakelaar.' -ForegroundColor Yellow
            }
        }
    } else {
        Write-Warn ("Kon '$Database' niet bereiken via psql: " + ($res.Output -join ' '))
        Write-Warn 'Database-check overgeslagen. We gaan toch door.'
        $moduleInstalled = $true
    }
} else {
    Write-Warn "psql niet gevonden op: $psqlExe"
    Write-Warn 'Database-check overgeslagen.'
    $moduleInstalled = $true
}

if (-not $moduleInstalled) {
    $env:PGPASSWORD = ''
    exit 1
}

$Database = $detectedDatabase

# ---------------------------------------------------------------------------
# Stap 2: Odoo service vinden en stoppen
# ---------------------------------------------------------------------------

Write-Step 'Stap 2/5 -- Odoo Windows-service stoppen'

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
# Stap 3: Tests uitvoeren — output naar console EN logbestand
# ---------------------------------------------------------------------------

Write-Step 'Stap 3/5 -- Tests uitvoeren (dit duurt 2-5 minuten)'
Write-Host '    Odoo schrijft output naar zijn eigen logfile; die lezen we na afloop uit.' -ForegroundColor DarkGray
Write-Host '    Wacht geduldig...' -ForegroundColor DarkGray
Write-Host ''

# --log-level test: geeft test-specifieke regels (PASS/FAIL/ERROR).
# Geen --logfile override: Odoo schrijft naar het pad uit odoo.conf.
# We lezen die logfile na afloop uit via een byte-offset.
$testArgs = @(
    $odooBin,
    '--config',        $odooConf,
    '--database',      $Database,
    '--update',        $ModuleName,
    '--test-enable',
    '--stop-after-init',
    '--log-level',     'test',
    '--no-http',
    '--without-demo',  'all'
)

# Sla de huidige grootte van Odoo's logfile op (offset) zodat we alleen
# de uitvoer van deze testrun terugzien.
$odooLogOffset = 0L
if ($odooLogFile -and (Test-Path $odooLogFile)) {
    $odooLogOffset = (Get-Item $odooLogFile).Length
    Write-Host "    Odoo logfile : $odooLogFile" -ForegroundColor DarkGray
    Write-Host "    Startpositie : $odooLogOffset bytes" -ForegroundColor DarkGray
} elseif ($odooLogFile) {
    Write-Warn "Odoo logfile niet gevonden op: $odooLogFile"
} else {
    Write-Warn 'Geen logfile gevonden in odoo.conf. Output kan ontbreken.'
}
Write-Host ''

$allOutput = [System.Collections.Generic.List[string]]::new()
$startTime = Get-Date

$prev = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
& $pythonExe @testArgs 2>&1 | Out-Null   # Odoo logt intern; stdout/stderr zijn leeg
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $prev

$duration = [int]((Get-Date) - $startTime).TotalSeconds

# Lees testuitvoer uit Odoo's logfile vanaf de opgeslagen offset
if ($odooLogFile -and (Test-Path $odooLogFile)) {
    Write-Host '    Testuitvoer laden uit Odoo logfile...' -ForegroundColor DarkGray
    $stream = [System.IO.FileStream]::new(
        $odooLogFile,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite
    )
    $stream.Seek($odooLogOffset, [System.IO.SeekOrigin]::Begin) | Out-Null
    $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8)
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        $allOutput.Add($line)
        if ($line -match 'FAIL:|AssertionError') {
            Write-Host "  $line" -ForegroundColor Red
        } elseif ($line -match ' ERROR ') {
            Write-Host "  $line" -ForegroundColor Red
        } elseif ($line -match 'ok$|\.\.\.ok|\.\.\. ok') {
            Write-Host "  $line" -ForegroundColor Green
        } elseif ($line -match 'WARNING') {
            Write-Host "  $line" -ForegroundColor Yellow
        } else {
            Write-Host "  $line"
        }
    }
    $reader.Close()
    $stream.Close()
} else {
    Write-Warn 'Kon Odoo logfile niet lezen. Controleer logfile= in odoo.conf.'
}

# Logbestand opslaan
$allOutput | Out-File -FilePath $logFile -Encoding utf8
Write-Host ''
Write-Host "    Klaar na $duration seconden. Log opgeslagen: $logFile" -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# Stap 4: Resultaten analyseren
# ---------------------------------------------------------------------------

Write-Step 'Stap 4/5 -- Testresultaten analyseren'

$failLines   = @($allOutput | Where-Object { $_ -match 'FAIL:|AssertionError' })
$errorLines  = @($allOutput | Where-Object { $_ -match ' ERROR ' -and $_ -notmatch 'test_enable' })
$testSummary = @($allOutput | Where-Object { $_ -match '\d+ test' -or $_ -match 'Ran \d+' })
$zeroTests   = @($allOutput | Where-Object { $_ -match '0 tests' -or $_ -match '0 failed.*0 test' })

Write-Host ''
Write-Host '  --- Samenvatting ---' -ForegroundColor White

if ($testSummary) {
    foreach ($line in $testSummary | Select-Object -Last 5) {
        $trimmed = $line -replace '^.*?(WARNING|INFO|ERROR)\s+\S+\s+', ''
        Write-Host "    $trimmed" -ForegroundColor White
    }
}

Write-Host ''

if ($zeroTests -and -not $failLines -and -not $errorLines) {
    Write-Warn '0 tests gevonden. Mogelijke oorzaken:'
    Write-Warn '  1. De module is niet geinstalleerd in de database.'
    Write-Warn ('     Controleer: ' + "psql -U openpg -d `"$Database`" -c `"SELECT state FROM ir_module_module WHERE name='$ModuleName';`"")
    Write-Warn '  2. De database naam in odoo.conf overschrijft de -d parameter.'
    Write-Warn ('     Controleer odoo.conf op "db_name =" of "dbfilter =".')
    Write-Warn '  3. Installeer de module eerst via Odoo UI of voer deploy_update.cmd -UpgradeModule uit.'
} elseif ($failLines.Count -eq 0 -and $errorLines.Count -eq 0) {
    Write-OK 'Geen FAIL of ERROR gevonden.'
    Write-OK 'Alle tests zijn geslaagd.'
} else {
    if ($failLines.Count -gt 0) {
        Write-Fail ("$($failLines.Count) FAIL(s) gevonden:")
        foreach ($line in $failLines | Select-Object -First 15) {
            Write-Host "      $line" -ForegroundColor Red
        }
    }
    if ($errorLines.Count -gt 0) {
        Write-Fail ("$($errorLines.Count) ERROR(s) gevonden (eerste 5):")
        foreach ($line in $errorLines | Select-Object -First 5) {
            Write-Host "      $line" -ForegroundColor Red
        }
    }
}

Write-Host ''
Write-Host "  Volledig logbestand: $logFile" -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# Stap 5: Odoo service herstarten
# ---------------------------------------------------------------------------

if ($SkipServiceRestart) {
    Write-Step 'Stap 5/5 -- Service herstart overgeslagen (-SkipServiceRestart)'
    Write-Warn 'Odoo draait NIET. Start handmatig via services.msc.'
} else {
    Write-Step ("Stap 5/5 -- Odoo-service herstarten ('" + $odooService.Name + "')")
    Write-Host '    Service starten...' -ForegroundColor DarkGray
    Start-Service -Name $odooService.Name
    $odooService.WaitForStatus('Running', [TimeSpan]::FromMinutes(3))
    Write-OK 'Odoo draait weer.'
}

# ---------------------------------------------------------------------------
# Eindstatus
# ---------------------------------------------------------------------------

Write-Host ''
$color = if ($exitCode -eq 0 -and $failLines.Count -eq 0) { 'Green' } else { 'Red' }
Write-Host '====================================================' -ForegroundColor $color
if ($exitCode -eq 0 -and $failLines.Count -eq 0) {
    Write-Host '  Tests voltooid -- geen fouten gevonden            ' -ForegroundColor $color
} else {
    Write-Host '  Tests voltooid -- controleer het logbestand       ' -ForegroundColor $color
}
Write-Host '====================================================' -ForegroundColor $color
Write-Host ''
Write-Host '  Odoo       : http://172.27.131.3:8069/odoo/payroll' -ForegroundColor White
Write-Host "  Logbestand : $logFile" -ForegroundColor White
Write-Host ''

exit $exitCode
