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


function Get-OdooVisibleDatabases {
    param([string]$BaseUrl = 'http://localhost:8069')

    if ($DryRun) {
        return @()
    }

    try {
        $selectorUrl = $BaseUrl.TrimEnd('/') + '/web/database/selector'
        $selectorPage = Invoke-WebRequest -UseBasicParsing -Uri $selectorUrl
    }
    catch {
        return @()
    }

    return @(
        [Regex]::Matches($selectorPage.Content, 'href="/odoo\?db=([^"&]+)"') |
        ForEach-Object { [Uri]::UnescapeDataString($_.Groups[1].Value).Trim() } |
        Where-Object { $_ } |
        Select-Object -Unique
    )
}


function Add-UniqueCandidate {
    param(
        [System.Collections.Generic.List[string]]$Candidates,
        [string]$Value
    )

    if ($Value -and (-not $Candidates.Contains($Value))) {
        $null = $Candidates.Add($Value)
    }
}


function Get-DatabaseCandidates {
    param(
        [string]$RequestedDatabase,
        [string[]]$AvailableDatabases,
        [string[]]$OdooVisibleDatabases
    )

    $candidates = [System.Collections.Generic.List[string]]::new()

    if ($AvailableDatabases -contains $RequestedDatabase) {
        Add-UniqueCandidate -Candidates $candidates -Value $RequestedDatabase
    }

    foreach ($databaseName in ($OdooVisibleDatabases | Where-Object { $_ -notin @('postgres') -and $AvailableDatabases -contains $_ })) {
        Add-UniqueCandidate -Candidates $candidates -Value $databaseName
    }

    foreach ($databaseName in ($AvailableDatabases | Where-Object { $_ -notin @('postgres') })) {
        Add-UniqueCandidate -Candidates $candidates -Value $databaseName
    }

    return @($candidates.ToArray())
}


function Get-OdooLoginPageState {
    param(
        [string]$DatabaseName,
        [string]$LoginName
    )

    $encodedDatabase = [Uri]::EscapeDataString($DatabaseName)
    $encodedLogin = [Uri]::EscapeDataString($LoginName)
    $loginUrl = "http://localhost:8069/web/login?db=$encodedDatabase&login=$encodedLogin"

    try {
        $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
        $loginPage = Invoke-WebRequest -UseBasicParsing -WebSession $session -Uri $loginUrl
    }
    catch {
        return [PSCustomObject]@{
            Success = $false
            LoginUrl = $loginUrl
            Session = $null
            CsrfToken = $null
            Detail = $_.Exception.Message
        }
    }

    $loginPageUri = $loginPage.BaseResponse.ResponseUri.AbsoluteUri
    if ($loginPageUri -match '/web/database/selector(?:$|\?)') {
        return [PSCustomObject]@{
            Success = $false
            LoginUrl = $loginUrl
            Session = $session
            CsrfToken = $null
            Detail = "Odoo redirected to the database selector at $loginPageUri"
        }
    }

    if ($loginPage.Content -notmatch 'name="csrf_token" value="([^"]+)"') {
        $pageDiagnostic = Get-OdooPageDiagnostic -Html $loginPage.Content
        $detail = "Could not find a CSRF token on the Odoo login page at $loginUrl."
        if ($pageDiagnostic) {
            $detail = "$detail Page detail: $pageDiagnostic"
        }

        return [PSCustomObject]@{
            Success = $false
            LoginUrl = $loginUrl
            Session = $session
            CsrfToken = $null
            Detail = $detail
        }
    }

    return [PSCustomObject]@{
        Success = $true
        LoginUrl = $loginUrl
        Session = $session
        CsrfToken = $Matches[1]
        Detail = $null
    }
}


function Test-OdooCredentials {
    param(
        $PageState,
        [string]$DatabaseName,
        [string]$LoginName,
        [string]$Password
    )

    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -WebSession $PageState.Session `
            -Method Post `
            -Uri 'http://localhost:8069/web/login' `
            -Body @{
                csrf_token = $PageState.CsrfToken
                db = $DatabaseName
                login = $LoginName
                password = $Password
                type = 'password'
                redirect = ''
            }
    }
    catch {
        return [PSCustomObject]@{
            Success = $false
            LoginUrl = $PageState.LoginUrl
            RedirectUri = $null
            Detail = $_.Exception.Message
        }
    }

    $redirectUri = $response.BaseResponse.ResponseUri.AbsoluteUri
    if ($redirectUri -notmatch '/odoo(?:$|\?)') {
        $pageDiagnostic = Get-OdooPageDiagnostic -Html $response.Content
        $detail = "The local login validation did not end on /odoo. Final URL: $redirectUri"
        if ($pageDiagnostic) {
            $detail = "$detail. Page detail: $pageDiagnostic"
        }

        return [PSCustomObject]@{
            Success = $false
            LoginUrl = $PageState.LoginUrl
            RedirectUri = $redirectUri
            Detail = $detail
        }
    }

    return [PSCustomObject]@{
        Success = $true
        LoginUrl = $PageState.LoginUrl
        RedirectUri = $redirectUri
        Detail = $null
    }
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
 $odooVisibleDatabases = @()
 $loginUrl = "http://localhost:8069/web/login?db=$([Uri]::EscapeDataString($Database))&login=$([Uri]::EscapeDataString($Login))"
if (-not $DryRun) {
    $availableDatabases = Get-AvailableDatabases `
        -PsqlPath $psqlPath `
        -DbHost $dbHost `
        -DbPort $dbPort `
        -DbUser $dbUser `
        -DbPassword $dbPassword
    $odooVisibleDatabases = Get-OdooVisibleDatabases
    $candidateDatabases = Get-DatabaseCandidates `
        -RequestedDatabase $Database `
        -AvailableDatabases $availableDatabases `
        -OdooVisibleDatabases $odooVisibleDatabases

    if ($candidateDatabases.Count -eq 0) {
        throw "No non-system PostgreSQL databases were found. Existing databases: $($availableDatabases -join ', ')"
    }

    Write-Step "Resetting password for '$Login'"
    Write-Step "Validating the login against the local Odoo web server"

    $requestedDatabase = $Database
    $validationFailures = [System.Collections.Generic.List[string]]::new()
    $validationResult = $null

    foreach ($candidateDatabase in $candidateDatabases) {
        $pageState = Get-OdooLoginPageState -DatabaseName $candidateDatabase -LoginName $Login
        if (-not $pageState.Success) {
            $null = $validationFailures.Add("${candidateDatabase}: $($pageState.Detail)")
            continue
        }

        $updatedUserId = Invoke-PsqlCapture `
            -PsqlPath $psqlPath `
            -DbHost $dbHost `
            -DbPort $dbPort `
            -DbUser $dbUser `
            -DbPassword $dbPassword `
            -DatabaseName $candidateDatabase `
            -Sql "update res_users set password = '$passwordSqlLiteral' where login = '$loginSqlLiteral' returning id;"

        if (-not $updatedUserId) {
            $knownLogins = Invoke-PsqlCapture `
                -PsqlPath $psqlPath `
                -DbHost $dbHost `
                -DbPort $dbPort `
                -DbUser $dbUser `
                -DbPassword $dbPassword `
                -DatabaseName $candidateDatabase `
                -Sql 'select login from res_users order by id;'

            $null = $validationFailures.Add("${candidateDatabase}: login '$Login' was not found. Known logins: $knownLogins")
            continue
        }

        $candidateValidation = Test-OdooCredentials `
            -PageState $pageState `
            -DatabaseName $candidateDatabase `
            -LoginName $Login `
            -Password $TemporaryPassword

        if ($candidateValidation.Success) {
            $Database = $candidateDatabase
            $databaseSqlLiteral = Convert-ToSqlLiteral -Value $Database
            $loginUrl = $candidateValidation.LoginUrl
            $validationResult = $candidateValidation

            if ($Database -ne $requestedDatabase) {
                Write-Host "Using working Odoo database '$Database' instead of '$requestedDatabase'." -ForegroundColor Yellow
            }

            break
        }

        $null = $validationFailures.Add("${candidateDatabase}: $($candidateValidation.Detail)")
    }

    if (-not $validationResult) {
        $visibleText = if ($odooVisibleDatabases.Count -gt 0) { $odooVisibleDatabases -join ', ' } else { '(none detected from /web/database/selector)' }
        throw "Could not repair the local login for '$Login'. Attempted databases: $($validationFailures -join ' || '). PostgreSQL databases: $($availableDatabases -join ', '). Odoo-visible databases: $visibleText"
    }
}
else {
    Write-Step "Resetting password for '$Login'"
    Write-Host "[dry-run] Password reset will use database '$Database'"

    Write-Step "Validating the login against the local Odoo web server"
    Write-Host "[dry-run] Validate HTTP login against $loginUrl"
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