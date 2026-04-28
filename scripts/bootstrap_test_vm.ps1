[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Database,

    [string]$OdooRoot = "C:\Program Files\Odoo 18.0e.20260407",
    [string]$AddonsRoot = "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0",
    [string]$RepoUrl = "https://github.com/LeoRanoe/l10n_sr_hr_payroll.git",
    [string]$ModuleName = "l10n_sr_hr_payroll",

    [ValidateSet("interactive", "skip")]
    [string]$PostgreSqlInstallMode = "interactive",

    [string]$PostgreSqlPackageId = "PostgreSQL.PostgreSQL.16",
    [string]$PostgreSqlAdminUser = "postgres",
    [Parameter(Mandatory = $true)]
    [SecureString]$PostgreSqlAdminPassword,

    [switch]$RegisterScheduledTask,
    [ValidateRange(5, 1440)]
    [int]$CheckEveryMinutes = 15,
    [switch]$RunTests,
    [switch]$ForceClean,
    [switch]$SkipGitInstall,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"


function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}


function Format-Command {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    $parts = @($FilePath) + $Arguments
    return ($parts | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + $_.Replace('"', '\"') + '"'
        }
        else {
            $_
        }
    }) -join " "
}


function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @(),

        [string]$Description = $FilePath,

        [switch]$CaptureOutput
    )

    $commandText = Format-Command -FilePath $FilePath -Arguments $Arguments

    if ($DryRun) {
        Write-Host "[dry-run] $commandText"
        if ($CaptureOutput) {
            return ""
        }
        return
    }

    if ($CaptureOutput) {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            $output | ForEach-Object { Write-Host $_ }
            throw "$Description failed with exit code $exitCode."
        }
        return ($output -join [Environment]::NewLine).Trim()
    }

    & $FilePath @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Description failed with exit code $exitCode."
    }
}


function Resolve-UnresolvedPath {
    param([string]$PathValue)

    if (-not $PathValue) {
        return $null
    }

    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PathValue)
}


function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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


function New-DirectoryIfMissing {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        return
    }

    if ($DryRun) {
        Write-Host "[dry-run] New-Item -ItemType Directory -Path $Path -Force"
        return
    }

    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}


function Convert-SecureStringToPlainText {
    param([SecureString]$Value)

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}


function Get-PostgreSqlService {
    $services = @(Get-Service -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match 'postgres' -or $_.DisplayName -match 'postgres'
    })

    if ($services.Count -eq 0) {
        return $null
    }

    return $services | Sort-Object Name | Select-Object -First 1
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


function Get-WingetInstallerMetadata {
    param([string]$PackageId)

    $wingetPath = (Get-Command winget -ErrorAction SilentlyContinue).Source
    if (-not $wingetPath) {
        throw "winget is not available, so the PostgreSQL installer metadata cannot be resolved automatically."
    }

    $output = Invoke-ExternalCommand `
        -FilePath $wingetPath `
        -Arguments @("show", "--id", $PackageId, "--accept-source-agreements") `
        -Description "winget show $PackageId" `
        -CaptureOutput

    $url = $null
    $sha256 = $null

    foreach ($line in ($output -split [Environment]::NewLine)) {
        if (-not $url -and ($line -match '^\s*Installer Url:\s*(\S+)\s*$')) {
            $url = $Matches[1]
            continue
        }

        if (-not $sha256 -and ($line -match '^\s*Installer SHA256:\s*([A-Fa-f0-9]+)\s*$')) {
            $sha256 = $Matches[1].ToUpperInvariant()
        }
    }

    if (-not $url) {
        throw "Could not read the PostgreSQL installer URL from winget metadata for package '$PackageId'."
    }

    return [pscustomobject]@{
        Url = $url
        Sha256 = $sha256
    }
}


function Install-PostgreSqlViaDirectDownload {
    param([string]$PackageId)

    $metadata = Get-WingetInstallerMetadata -PackageId $PackageId
    $downloadDir = Join-Path $env:TEMP "l10n_sr_hr_payroll-bootstrap"
    $installerFileName = [System.IO.Path]::GetFileName(([Uri]$metadata.Url).AbsolutePath)
    $installerPath = Join-Path $downloadDir $installerFileName

    New-DirectoryIfMissing -Path $downloadDir

    Write-Step "Downloading PostgreSQL installer directly"
    Invoke-ExternalCommand `
        -FilePath "curl.exe" `
        -Arguments @("-L", "--fail", "--retry", "3", "--output", $installerPath, $metadata.Url) `
        -Description "curl PostgreSQL installer"

    if ($metadata.Sha256) {
        if ($DryRun) {
            Write-Host "[dry-run] Get-FileHash -Algorithm SHA256 -Path $installerPath"
        }
        else {
            $downloadHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installerPath).Hash.ToUpperInvariant()
            if ($downloadHash -ne $metadata.Sha256) {
                throw "Downloaded PostgreSQL installer hash '$downloadHash' does not match expected '$($metadata.Sha256)'."
            }
        }
    }

    Write-Host "If the PostgreSQL installer asks for an admin password, use the same value you passed in -PostgreSqlAdminPassword." -ForegroundColor Yellow

    Write-Step "Launching PostgreSQL installer directly"
    if ($DryRun) {
        Write-Host "[dry-run] Start-Process -FilePath $installerPath -Wait"
        return
    }

    $process = Start-Process -FilePath $installerPath -PassThru -Wait
    if ($process.ExitCode -ne 0) {
        throw "Direct PostgreSQL installer exited with code $($process.ExitCode)."
    }
}


function Install-GitIfMissing {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        return
    }

    if ($SkipGitInstall) {
        throw "Git is not available in PATH and -SkipGitInstall was specified. Install Git or remove -SkipGitInstall."
    }

    $wingetPath = (Get-Command winget -ErrorAction SilentlyContinue).Source
    if (-not $wingetPath) {
        throw "Git is not available in PATH and winget is not installed. Install Git manually before rerunning this script."
    }

    Write-Step "Installing Git with winget"
    Invoke-ExternalCommand `
        -FilePath $wingetPath `
        -Arguments @(
            "install",
            "--id", "Git.Git",
            "--exact",
            "--silent",
            "--accept-source-agreements",
            "--accept-package-agreements"
        ) `
        -Description "winget install Git.Git"

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git installation finished but git is still not available in PATH. Open a new PowerShell session and rerun the script."
    }
}


function Install-PostgreSqlIfMissing {
    param([string]$ResolvedOdooRoot)

    $service = Get-PostgreSqlService
    $psqlPath = Get-PsqlPath -ResolvedOdooRoot $ResolvedOdooRoot

    if ($service -or $psqlPath) {
        return
    }

    if ($PostgreSqlInstallMode -eq "skip") {
        throw "PostgreSQL was not found and -PostgreSqlInstallMode skip was specified. Install PostgreSQL manually or rerun with -PostgreSqlInstallMode interactive."
    }

    $wingetPath = (Get-Command winget -ErrorAction SilentlyContinue).Source
    if (-not $wingetPath) {
        throw "PostgreSQL was not found and winget is not available. Install PostgreSQL manually before rerunning this script."
    }

    Write-Step "Installing PostgreSQL with winget"
    try {
        Invoke-ExternalCommand `
            -FilePath $wingetPath `
            -Arguments @(
                "install",
                "--id", $PostgreSqlPackageId,
                "--exact",
                "--interactive",
                "--accept-source-agreements",
                "--accept-package-agreements"
            ) `
            -Description "winget install $PostgreSqlPackageId"
    }
    catch {
        Write-Host "winget install failed: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Falling back to a direct PostgreSQL installer download because the winget download step can fail with HTTP 403 on some VMs." -ForegroundColor Yellow
        Install-PostgreSqlViaDirectDownload -PackageId $PostgreSqlPackageId
    }

    $script:postInstallMessage = "During the PostgreSQL installer wizard, use the same admin password you passed in -PostgreSqlAdminPassword so the rest of this script can create the Odoo role automatically."
    Write-Host $script:postInstallMessage -ForegroundColor Yellow
}


function Start-PostgreSqlServiceIfNeeded {
    $service = Get-PostgreSqlService
    if (-not $service) {
        throw "PostgreSQL does not appear to be installed. No Windows service with 'postgres' in the name was found after installation."
    }

    if ($service.Status -eq 'Running') {
        return $service.Name
    }

    Write-Step "Starting PostgreSQL service '$($service.Name)'"

    if ($DryRun) {
        Write-Host "[dry-run] Start-Service -Name $($service.Name)"
        return $service.Name
    }

    Start-Service -Name $service.Name
    $service.WaitForStatus('Running', [TimeSpan]::FromMinutes(2))
    return $service.Name
}


function Set-OdooDatabaseRole {
    param(
        [string]$ResolvedOdooRoot,
        [string]$PsqlPath
    )

    $configPath = Join-Path $ResolvedOdooRoot "server\odoo.conf"
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw "Could not find Odoo config at $configPath."
    }

    $dbHost = Get-IniSetting -FilePath $configPath -Name "db_host"
    $dbPort = Get-IniSetting -FilePath $configPath -Name "db_port"
    $dbUser = Get-IniSetting -FilePath $configPath -Name "db_user"
    $dbPassword = Get-IniSetting -FilePath $configPath -Name "db_password"

    if (-not $dbHost -or $dbHost -in @("False", "false")) {
        $dbHost = "localhost"
    }
    if (-not $dbPort -or $dbPort -in @("False", "false")) {
        $dbPort = "5432"
    }
    if (-not $dbUser -or $dbUser -in @("False", "false")) {
        throw "db_user is not set in $configPath."
    }
    if (-not $dbPassword -or $dbPassword -in @("False", "false")) {
        throw "db_password is not set in $configPath."
    }

    $sql = @"
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$dbUser') THEN
        EXECUTE format('CREATE ROLE %I WITH LOGIN PASSWORD %L CREATEDB', '$dbUser', '$dbPassword');
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L CREATEDB', '$dbUser', '$dbPassword');
    END IF;
END
$$;
"@

    $sqlFile = Join-Path $env:TEMP "ensure_odoo_role_$($ModuleName).sql"

    if ($DryRun) {
        Write-Host "[dry-run] Set-Content -Path $sqlFile -Value <ensure role sql>"
    }
    else {
        Set-Content -LiteralPath $sqlFile -Value $sql -Encoding ASCII
    }

    Write-Step "Ensuring PostgreSQL role '$dbUser' matches Odoo config"

    $adminPasswordPlainText = Convert-SecureStringToPlainText -Value $PostgreSqlAdminPassword
    $previousPassword = $env:PGPASSWORD
    try {
        $env:PGPASSWORD = $adminPasswordPlainText
        Invoke-ExternalCommand `
            -FilePath $PsqlPath `
            -Arguments @(
                "-h", $dbHost,
                "-p", $dbPort,
                "-U", $PostgreSqlAdminUser,
                "-d", "postgres",
                "-v", "ON_ERROR_STOP=1",
                "-f", $sqlFile
            ) `
            -Description "psql role bootstrap"
    }
    finally {
        $adminPasswordPlainText = $null
        $env:PGPASSWORD = $previousPassword
        if ((-not $DryRun) -and (Test-Path -LiteralPath $sqlFile)) {
            Remove-Item -LiteralPath $sqlFile -Force
        }
    }
}


function Invoke-StagingSync {
    param([string]$ResolvedAddonsRoot)

    $moduleRoot = Join-Path $ResolvedAddonsRoot $ModuleName
    $syncScript = Join-Path $moduleRoot "scripts\sync_from_staging.ps1"

    if (-not (Test-Path -LiteralPath $syncScript)) {
        $gitPath = (Get-Command git -ErrorAction Stop).Source
        if (-not (Test-Path -LiteralPath $moduleRoot)) {
            Write-Step "Cloning staging branch into $moduleRoot"
            Invoke-ExternalCommand `
                -FilePath $gitPath `
                -Arguments @("clone", "--branch", "staging", "--single-branch", $RepoUrl, $moduleRoot) `
                -Description "git clone"
        }
    }

    if (-not (Test-Path -LiteralPath $syncScript)) {
        throw "Could not find $syncScript after cloning the repository."
    }

    Write-Step "Running staging sync and module installation"

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $syncScript,
        "-AddonsRoot", $ResolvedAddonsRoot,
        "-OdooRoot", $OdooRoot,
        "-Database", $Database,
        "-Action", "install"
    )

    if ($RegisterScheduledTask) {
        $arguments += "-RegisterScheduledTask"
        $arguments += "-CheckEveryMinutes"
        $arguments += "$CheckEveryMinutes"
    }

    if ($RunTests) {
        $arguments += "-RunTests"
    }

    if ($ForceClean) {
        $arguments += "-ForceClean"
    }

    if ($DryRun) {
        $arguments += "-DryRun"
    }

    Invoke-ExternalCommand `
        -FilePath (Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe") `
        -Arguments $arguments `
        -Description "sync_from_staging.ps1"
}


if (-not (Test-IsAdministrator)) {
    if ($DryRun) {
        Write-Host "[dry-run] Skipping elevation check. A real run must use an elevated PowerShell window." -ForegroundColor Yellow
    }
    else {
        throw "Run this script from an elevated PowerShell window."
    }
}

$resolvedOdooRoot = Resolve-UnresolvedPath -PathValue $OdooRoot
$resolvedAddonsRoot = if (Test-Path -LiteralPath $AddonsRoot) {
    Resolve-UnresolvedPath -PathValue $AddonsRoot
}
else {
    $AddonsRoot
}

New-DirectoryIfMissing -Path $resolvedAddonsRoot
Install-GitIfMissing
Install-PostgreSqlIfMissing -ResolvedOdooRoot $resolvedOdooRoot
$postgresServiceName = Start-PostgreSqlServiceIfNeeded
$psqlPath = Get-PsqlPath -ResolvedOdooRoot $resolvedOdooRoot

if (-not $psqlPath) {
    throw "PostgreSQL service '$postgresServiceName' is running, but psql.exe could not be found. Install PostgreSQL client tools or rerun after opening a new PowerShell session."
}

Set-OdooDatabaseRole -ResolvedOdooRoot $resolvedOdooRoot -PsqlPath $psqlPath
Invoke-StagingSync -ResolvedAddonsRoot $resolvedAddonsRoot