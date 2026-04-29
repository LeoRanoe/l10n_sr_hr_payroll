[CmdletBinding()]
param(
    [string]$OdooRoot = "C:\Program Files\Odoo 18.0e.20260407",
    [string]$Database = "Salarisverwerking-Module",
    [string]$Login = "stagiaire2.rpbg@gmail.com",
    [string]$TemporaryPassword = "Welkom1234",
    [switch]$OpenBrowser,
    [switch]$OpenInPrivate,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"


function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}


function Resolve-UnresolvedPath {
    param([string]$PathValue)

    if (-not $PathValue) {
        return $null
    }

    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PathValue)
}


function Get-IniSetting {
    param(
        [string]$FilePath,
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $FilePath)) {
        return $null
    }

    $pattern = '^\s*' + [Regex]::Escape($Name) + '\s*=\s*(.*)$'
    foreach ($line in Get-Content -LiteralPath $FilePath) {
        if ($line -match $pattern) {
            return $Matches[1].Trim()
        }
    }

    return $null
}


function Convert-ToSqlLiteral {
    param([string]$Value)

    return $Value.Replace("'", "''")
}


function Get-PsqlPath {
    param([string]$ResolvedOdooRoot)

    $candidates = @(
        (Join-Path $ResolvedOdooRoot "PostgreSQL\bin\psql.exe")
    )

    $versionRoots = @(
        "C:\Program Files\PostgreSQL",
        "C:\Program Files (x86)\PostgreSQL"
    )

    foreach ($root in $versionRoots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        $candidate = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "bin\psql.exe" } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1

        if ($candidate) {
            $candidates += $candidate
        }
    }

    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}


function Invoke-PsqlCapture {
    param(
        [string]$PsqlPath,
        [string]$DbHost,
        [string]$DbPort,
        [string]$DbUser,
        [string]$DbPassword,
        [string]$DatabaseName,
        [string]$Sql
    )

    $previousPassword = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = $DbPassword

        if ($DryRun) {
            Write-Host "[dry-run] $PsqlPath -h $DbHost -p $DbPort -U $DbUser -d $DatabaseName -t -A -v ON_ERROR_STOP=1 -c <sql>"
            return ""
        }

        $output = & $PsqlPath @(
            '-h', $DbHost,
            '-p', $DbPort,
            '-U', $DbUser,
            '-d', $DatabaseName,
            '-t',
            '-A',
            '-v', 'ON_ERROR_STOP=1',
            '-c', $Sql
        ) 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            $output | ForEach-Object { Write-Host $_ }
            throw "psql failed with exit code $exitCode."
        }

        return (($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine).Trim()
    }
    finally {
        $env:PGPASSWORD = $previousPassword
    }
}


function Get-AvailableDatabases {
    param(
        [string]$PsqlPath,
        [string]$DbHost,
        [string]$DbPort,
        [string]$DbUser,
        [string]$DbPassword
    )

    $databaseList = Invoke-PsqlCapture `
        -PsqlPath $PsqlPath `
        -DbHost $DbHost `
        -DbPort $DbPort `
        -DbUser $DbUser `
        -DbPassword $DbPassword `
        -DatabaseName 'postgres' `
        -Sql 'select datname from pg_database where datistemplate = false order by datname;'

    return @(
        $databaseList -split "`r?`n" |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
    )
}


function Open-LoginBrowser {
    param(
        [string]$LoginUrl,
        [switch]$PrivateWindow
    )

    if ($DryRun) {
        Write-Host "[dry-run] Open browser at $LoginUrl"
        return
    }

    if ($PrivateWindow) {
        $edge = Get-Command msedge.exe -ErrorAction SilentlyContinue
        if ($edge) {
            Start-Process -FilePath $edge.Source -ArgumentList @('--inprivate', $LoginUrl)
            return
        }

        $chrome = Get-Command chrome.exe -ErrorAction SilentlyContinue
        if ($chrome) {
            Start-Process -FilePath $chrome.Source -ArgumentList @('--incognito', $LoginUrl)
            return
        }
    }

    Start-Process $LoginUrl
}


function Get-OdooPageDiagnostic {
    param([string]$Html)

    if (-not $Html) {
        return $null
    }

    $patterns = @(
        '(?is)<div[^>]*alert[^>]*>\s*(.*?)\s*</div>',
        '(?is)<h[1-3][^>]*>\s*(.*?)\s*</h[1-3]>',
        '(?is)<title>\s*(.*?)\s*</title>'
    )

    foreach ($pattern in $patterns) {
        if ($Html -match $pattern) {
            $text = [Regex]::Replace($Matches[1], '<[^>]+>', ' ')
            $text = [Regex]::Replace($text, '\s+', ' ').Trim()
            if ($text) {
                return $text
            }
        }
    }

    if ($Html -match 'Manage databases') {
        return 'Manage databases'
    }

    return $null
}


$resolvedOdooRoot = Resolve-UnresolvedPath -PathValue $OdooRoot
$configPath = Join-Path $resolvedOdooRoot "server\odoo.conf"

if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Could not find Odoo config at $configPath."
}

$dbHost = Get-IniSetting -FilePath $configPath -Name 'db_host'
$dbPort = Get-IniSetting -FilePath $configPath -Name 'db_port'
$dbUser = Get-IniSetting -FilePath $configPath -Name 'db_user'
$dbPassword = Get-IniSetting -FilePath $configPath -Name 'db_password'

if (-not $dbHost -or $dbHost -in @('False', 'false')) {
    $dbHost = 'localhost'
}

if (-not $dbPort -or $dbPort -in @('False', 'false')) {
    $dbPort = '5432'
}

if (-not $dbUser -or $dbUser -in @('False', 'false')) {
    throw "db_user is not set in $configPath."
}

if (-not $dbPassword -or $dbPassword -in @('False', 'false')) {
    throw "db_password is not set in $configPath."
}

$psqlPath = Get-PsqlPath -ResolvedOdooRoot $resolvedOdooRoot
if (-not $psqlPath) {
    throw "Could not find psql.exe. Install PostgreSQL client tools first."
}

$databaseSqlLiteral = Convert-ToSqlLiteral -Value $Database
$loginSqlLiteral = Convert-ToSqlLiteral -Value $Login
$passwordSqlLiteral = Convert-ToSqlLiteral -Value $TemporaryPassword

Write-Step "Checking whether database '$Database' exists"
$availableDatabases = @()
if (-not $DryRun) {
    $availableDatabases = Get-AvailableDatabases `
        -PsqlPath $psqlPath `
        -DbHost $dbHost `
        -DbPort $dbPort `
        -DbUser $dbUser `
        -DbPassword $dbPassword

    if ($availableDatabases -contains $Database) {
        $databaseSqlLiteral = Convert-ToSqlLiteral -Value $Database
    }
    else {
        $candidateDatabases = @(
            $availableDatabases | Where-Object { $_ -notin @('postgres') }
        )

        if ($candidateDatabases.Count -eq 1) {
            $Database = $candidateDatabases[0]
            $databaseSqlLiteral = Convert-ToSqlLiteral -Value $Database
            Write-Host "Requested database was not found. Falling back to the only detected Odoo database '$Database'." -ForegroundColor Yellow
        }
        else {
            throw "Database '$Database' does not exist. Existing databases: $($availableDatabases -join ', ')"
        }
    }
}

Write-Step "Resetting password for '$Login'"
$updatedUserId = Invoke-PsqlCapture `
    -PsqlPath $psqlPath `
    -DbHost $dbHost `
    -DbPort $dbPort `
    -DbUser $dbUser `
    -DbPassword $dbPassword `
    -DatabaseName $Database `
    -Sql "update res_users set password = '$passwordSqlLiteral' where login = '$loginSqlLiteral' returning id;"

if ((-not $DryRun) -and (-not $updatedUserId)) {
    $knownLogins = Invoke-PsqlCapture `
        -PsqlPath $psqlPath `
        -DbHost $dbHost `
        -DbPort $dbPort `
        -DbUser $dbUser `
        -DbPassword $dbPassword `
        -DatabaseName $Database `
        -Sql 'select login from res_users order by id;'

    throw "No Odoo user with login '$Login' was found in database '$Database'. Known logins: $knownLogins"
}

$encodedDatabase = [Uri]::EscapeDataString($Database)
$encodedLogin = [Uri]::EscapeDataString($Login)
$loginUrl = "http://localhost:8069/web/login?db=$encodedDatabase&login=$encodedLogin"

Write-Step "Validating the login against the local Odoo web server"
if ($DryRun) {
    Write-Host "[dry-run] Validate HTTP login against $loginUrl"
}
else {
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $loginPage = Invoke-WebRequest -UseBasicParsing -WebSession $session -Uri $loginUrl
    $loginPageUri = $loginPage.BaseResponse.ResponseUri.AbsoluteUri
    if ($loginPageUri -match '/web/database/selector(?:$|\?)') {
        throw "Database '$Database' is not available in the Odoo web server. Odoo redirected to the database selector at $loginPageUri. Existing PostgreSQL databases: $($availableDatabases -join ', ')"
    }

    if ($loginPage.Content -notmatch 'name="csrf_token" value="([^"]+)"') {
        $pageDiagnostic = Get-OdooPageDiagnostic -Html $loginPage.Content
        if ($pageDiagnostic) {
            throw "Could not find a CSRF token on the Odoo login page at $loginUrl. Page detail: $pageDiagnostic"
        }

        throw "Could not find a CSRF token on the Odoo login page at $loginUrl."
    }

    $csrfToken = $Matches[1]
    $response = Invoke-WebRequest `
        -UseBasicParsing `
        -WebSession $session `
        -Method Post `
        -Uri 'http://localhost:8069/web/login' `
        -Body @{
            csrf_token = $csrfToken
            db = $Database
            login = $Login
            password = $TemporaryPassword
            type = 'password'
            redirect = ''
        }

    $redirectUri = $response.BaseResponse.ResponseUri.AbsoluteUri
    if ($redirectUri -notmatch '/odoo(?:$|\?)') {
        $pageDiagnostic = Get-OdooPageDiagnostic -Html $response.Content
        if ($pageDiagnostic) {
            throw "The local login validation did not end on /odoo. Final URL: $redirectUri. Page detail: $pageDiagnostic"
        }

        throw "The local login validation did not end on /odoo. Final URL: $redirectUri"
    }
}

Write-Host ""
Write-Host 'Local Odoo login is ready.' -ForegroundColor Green
Write-Host "Database : $Database"
Write-Host "Email    : $Login"
Write-Host "Password : $TemporaryPassword"
Write-Host "URL      : $loginUrl"

if ($OpenBrowser -or $OpenInPrivate) {
    Open-LoginBrowser -LoginUrl $loginUrl -PrivateWindow:$OpenInPrivate
}