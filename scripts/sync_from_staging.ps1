[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Database,

    [ValidateSet("install", "update")]
    [string]$Action = "install",

    [string]$RepoUrl = "https://github.com/LeoRanoe/l10n_sr_hr_payroll.git",

    [string]$ModuleName = "l10n_sr_hr_payroll",
    [string]$AddonsRoot,
    [string]$ModuleRoot,
    [string]$OdooRoot,
    [string]$DataDir,

    [switch]$RunTests,
    [switch]$SkipOdoo,
    [switch]$RegisterScheduledTask,

    [ValidateRange(5, 1440)]
    [int]$CheckEveryMinutes = 15,

    [string]$TaskName = "Odoo staging updater - l10n_sr_hr_payroll",

    [switch]$ForceClean,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$isWindowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
$branch = "staging"


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


function Find-OdooRoot {
    param([string]$StartPath)

    $current = Get-Item -LiteralPath $StartPath
    while ($null -ne $current) {
        if (Test-Path -LiteralPath (Join-Path $current.FullName "server\odoo-bin")) {
            return $current.FullName
        }
        $current = $current.Parent
    }

    return $null
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


function Test-TcpEndpoint {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 2000
    )

    $tcpClient = New-Object System.Net.Sockets.TcpClient
    try {
        $asyncResult = $tcpClient.BeginConnect($HostName, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            return $false
        }

        $tcpClient.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $tcpClient.Dispose()
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


function Get-PgIsReadyPath {
    param([string]$ResolvedOdooRoot)

    $candidates = @(
        (Join-Path $ResolvedOdooRoot "PostgreSQL\bin\pg_isready.exe")
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
            ForEach-Object { Join-Path $_.FullName "bin\pg_isready.exe" } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1

        if ($candidate) {
            $candidates += $candidate
        }
    }

    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}


function Assert-PostgreSqlReady {
    param([string]$ResolvedOdooRoot)

    $configPath = Join-Path $ResolvedOdooRoot "server\odoo.conf"
    $dbHost = Get-IniSetting -FilePath $configPath -Name "db_host"
    $dbPortText = Get-IniSetting -FilePath $configPath -Name "db_port"

    if (-not $dbHost -or $dbHost -in @("False", "false")) {
        $dbHost = "localhost"
    }

    if (-not $dbPortText -or $dbPortText -in @("False", "false")) {
        $dbPort = 5432
    }
    else {
        $dbPort = [int]$dbPortText
    }

    $isLocalPostgres = $dbHost -in @("localhost", "127.0.0.1", "::1")
    $postgresService = if ($isLocalPostgres) { Get-PostgreSqlService } else { $null }
    $pgIsReadyPath = if ($isLocalPostgres) { Get-PgIsReadyPath -ResolvedOdooRoot $ResolvedOdooRoot } else { $null }

    if (Test-TcpEndpoint -HostName $dbHost -Port $dbPort) {
        return
    }

    if ($isLocalPostgres) {
        if ((-not $postgresService) -and (-not $pgIsReadyPath)) {
            throw "PostgreSQL was not found on this machine. Odoo is configured to use ${dbHost}:$dbPort in $configPath, but no Windows service with 'postgres' in its name and no PostgreSQL client tools were found. Install PostgreSQL on the VM or point odoo.conf to an existing PostgreSQL server before rerunning setup."
        }

        if ($postgresService -and ($postgresService.Status -ne 'Running')) {
            throw "PostgreSQL service '$($postgresService.Name)' is installed but not running. Start it with Start-Service $($postgresService.Name) and rerun setup."
        }

        throw "Could not connect to local PostgreSQL at ${dbHost}:$dbPort. Check that PostgreSQL is installed, running, and accepting TCP connections before rerunning setup."
    }

    throw "Could not connect to PostgreSQL at ${dbHost}:$dbPort from $configPath. Update the Odoo database settings or make that PostgreSQL server reachable before rerunning setup."
}


function Register-UpdateTask {
    param(
        [string]$ScriptPath,
        [string]$ResolvedAddonsRoot,
        [string]$ResolvedOdooRoot
    )

    if (-not $isWindowsHost) {
        throw "Scheduled task registration is only supported on Windows."
    }

    if (-not (Test-IsAdministrator)) {
        throw "Registering the scheduled task requires an elevated PowerShell session."
    }

    Import-Module ScheduledTasks -ErrorAction Stop

    $taskArguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $ScriptPath,
        "-Database", $Database,
        "-Action", "update",
        "-RepoUrl", $RepoUrl,
        "-ModuleName", $ModuleName,
        "-AddonsRoot", $ResolvedAddonsRoot,
        "-OdooRoot", $ResolvedOdooRoot
    )

    if ($RunTests) {
        $taskArguments += "-RunTests"
    }

    if ($ForceClean) {
        $taskArguments += "-ForceClean"
    }

    $argumentString = ($taskArguments | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + $_.Replace('"', '\"') + '"'
        }
        else {
            $_
        }
    }) -join " "

    if ($DryRun) {
        Write-Host "[dry-run] Register-ScheduledTask -TaskName $TaskName -Execute PowerShell.exe -Argument $argumentString"
        return
    }

    $actionObject = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument $argumentString
    $triggerObject = New-ScheduledTaskTrigger `
        -Once `
        -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $CheckEveryMinutes) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    $principalObject = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $actionObject `
        -Trigger $triggerObject `
        -Principal $principalObject `
        -Force | Out-Null

    Write-Host "Scheduled task '$TaskName' registered to poll origin/$branch every $CheckEveryMinutes minute(s)."
}


$gitPath = (Get-Command git -ErrorAction Stop).Source
$scriptModuleRoot = Split-Path -Parent $PSScriptRoot

if (-not $ModuleRoot) {
    if (Test-Path -LiteralPath (Join-Path $scriptModuleRoot "__manifest__.py")) {
        $ModuleRoot = $scriptModuleRoot
    }
    elseif ($AddonsRoot) {
        $ModuleRoot = Join-Path (Resolve-UnresolvedPath -PathValue $AddonsRoot) $ModuleName
    }
    else {
        throw "Pass -AddonsRoot or -ModuleRoot when the script is not already inside the module repository."
    }
}

$ModuleRoot = Resolve-UnresolvedPath -PathValue $ModuleRoot

if (-not $AddonsRoot) {
    $AddonsRoot = Split-Path -Parent $ModuleRoot
}

$AddonsRoot = Resolve-UnresolvedPath -PathValue $AddonsRoot

if (-not (Test-Path -LiteralPath $AddonsRoot)) {
    if ($DryRun) {
        Write-Host "[dry-run] New-Item -ItemType Directory -Path $AddonsRoot -Force"
    }
    else {
        New-Item -ItemType Directory -Path $AddonsRoot -Force | Out-Null
    }
}

$moduleAlreadyExists = Test-Path -LiteralPath $ModuleRoot
$changesDetected = $false

if (-not $moduleAlreadyExists) {
    Write-Step "Cloning $RepoUrl into $ModuleRoot"
    Invoke-ExternalCommand `
        -FilePath $gitPath `
        -Arguments @("clone", "--branch", $branch, "--single-branch", $RepoUrl, $ModuleRoot) `
        -Description "git clone"
    $changesDetected = $true
}

if (-not (Test-Path -LiteralPath (Join-Path $ModuleRoot ".git"))) {
    throw "$ModuleRoot exists but is not a Git repository."
}

$originUrl = Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "remote", "get-url", "origin") `
    -Description "git remote get-url" `
    -CaptureOutput

if ($originUrl -and ($originUrl.Trim() -ne $RepoUrl)) {
    throw "Remote origin URL '$originUrl' does not match the expected repo '$RepoUrl'. Pass -RepoUrl if this VM should use another remote."
}

$previousBranch = Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "branch", "--show-current") `
    -Description "git branch --show-current" `
    -CaptureOutput

Write-Step "Fetching origin/$branch"
Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "fetch", "origin", $branch, "--prune") `
    -Description "git fetch"

$worktreeStatus = Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "status", "--porcelain") `
    -Description "git status" `
    -CaptureOutput

if ($worktreeStatus) {
    if ($ForceClean) {
        Write-Step "Removing local changes before syncing with origin/$branch"
        Invoke-ExternalCommand `
            -FilePath $gitPath `
            -Arguments @("-C", $ModuleRoot, "reset", "--hard", "HEAD") `
            -Description "git reset --hard"
        Invoke-ExternalCommand `
            -FilePath $gitPath `
            -Arguments @("-C", $ModuleRoot, "clean", "-fd") `
            -Description "git clean"
    }
    else {
        throw "Local changes were found in $ModuleRoot. Commit, stash, or rerun with -ForceClean."
    }
}

$localBranch = Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "branch", "--list", $branch) `
    -Description "git branch --list" `
    -CaptureOutput

if ($localBranch) {
    Invoke-ExternalCommand `
        -FilePath $gitPath `
        -Arguments @("-C", $ModuleRoot, "checkout", $branch) `
        -Description "git checkout"
    Invoke-ExternalCommand `
        -FilePath $gitPath `
        -Arguments @("-C", $ModuleRoot, "branch", "--set-upstream-to", "origin/$branch", $branch) `
        -Description "git branch --set-upstream-to"
}
else {
    Invoke-ExternalCommand `
        -FilePath $gitPath `
        -Arguments @("-C", $ModuleRoot, "checkout", "-b", $branch, "--track", "origin/$branch") `
        -Description "git checkout -b"
}

if ($previousBranch -and ($previousBranch.Trim() -ne $branch)) {
    $changesDetected = $true
}

$localHead = Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "rev-parse", "HEAD") `
    -Description "git rev-parse HEAD" `
    -CaptureOutput

$remoteHead = Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "rev-parse", "origin/$branch") `
    -Description "git rev-parse origin head" `
    -CaptureOutput

if ($localHead -ne $remoteHead) {
    Write-Step "Fast-forwarding local $branch to origin/$branch"
    Invoke-ExternalCommand `
        -FilePath $gitPath `
        -Arguments @("-C", $ModuleRoot, "pull", "--ff-only", "origin", $branch) `
        -Description "git pull --ff-only"
    $changesDetected = $true
}

$currentCommit = Invoke-ExternalCommand `
    -FilePath $gitPath `
    -Arguments @("-C", $ModuleRoot, "rev-parse", "--short", "HEAD") `
    -Description "git rev-parse --short HEAD" `
    -CaptureOutput

Write-Host "Repository ready on $branch at commit $currentCommit."

if (-not $SkipOdoo) {
    if (-not $OdooRoot) {
        $OdooRoot = Find-OdooRoot -StartPath $ModuleRoot
    }

    if (-not $OdooRoot) {
        throw "Could not detect the Odoo root automatically. Pass -OdooRoot explicitly."
    }

    $OdooRoot = Resolve-UnresolvedPath -PathValue $OdooRoot

    if (-not $DataDir) {
        $DataDir = Join-Path $env:TEMP (Join-Path "odoo-data" (Join-Path $ModuleName $Database))
    }

    $DataDir = Resolve-UnresolvedPath -PathValue $DataDir

    if ($DryRun) {
        Write-Host "[dry-run] New-Item -ItemType Directory -Path $DataDir -Force"
    }
    else {
        New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    }

    if (($Action -eq "update") -and (-not $changesDetected)) {
        Write-Step "No new staging commits found. Skipping Odoo module update."
    }
    else {
        Assert-PostgreSqlReady -ResolvedOdooRoot $OdooRoot

        $pythonPath = Join-Path $OdooRoot "python\python.exe"
        if (-not (Test-Path -LiteralPath $pythonPath)) {
            $pythonPath = (Get-Command python -ErrorAction Stop).Source
        }

        $installScript = Join-Path $ModuleRoot "scripts\install_module.py"
        if (-not (Test-Path -LiteralPath $installScript)) {
            throw "Could not find $installScript."
        }

        Write-Step "Running Odoo module $Action for database '$Database'"

        $odooArguments = @(
            $installScript,
            "--database", $Database,
            "--action", $Action,
            "--odoo-root", $OdooRoot,
            "--extra-arg=--data-dir=$DataDir"
        )

        if ($RunTests) {
            $odooArguments += "--test-enable"
        }

        Invoke-ExternalCommand `
            -FilePath $pythonPath `
            -Arguments $odooArguments `
            -Description "Odoo module sync"
    }
}
else {
    Write-Step "Skipping Odoo install/update because -SkipOdoo was specified."
}

if ($RegisterScheduledTask) {
    $repoScriptPath = Join-Path $ModuleRoot "scripts\sync_from_staging.ps1"
    if (-not (Test-Path -LiteralPath $repoScriptPath)) {
        throw "Could not find $repoScriptPath for scheduled task registration."
    }

    Register-UpdateTask `
        -ScriptPath $repoScriptPath `
        -ResolvedAddonsRoot $AddonsRoot `
        -ResolvedOdooRoot $OdooRoot
}