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


function Invoke-GitCommand {
    param([string[]]$Arguments)

    $stdoutPath = Join-Path $env:TEMP ("git_stdout_{0}.log" -f [Guid]::NewGuid())
    $stderrPath = Join-Path $env:TEMP ("git_stderr_{0}.log" -f [Guid]::NewGuid())

    try {
        $process = Start-Process `
            -FilePath $gitPath `
            -ArgumentList $Arguments `
            -WorkingDirectory (Get-Location).Path `
            -Wait `
            -PassThru `
            -NoNewWindow `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        $stdoutLines = if (Test-Path -LiteralPath $stdoutPath) { @(Get-Content -LiteralPath $stdoutPath) } else { @() }
        $stderrLines = if (Test-Path -LiteralPath $stderrPath) { @(Get-Content -LiteralPath $stderrPath) } else { @() }
        $output = @($stdoutLines + $stderrLines)

        foreach ($line in $output) {
            if ($line) {
                Write-Host $line
            }
        }

        return [PSCustomObject]@{
            ExitCode = $process.ExitCode
            Output = (($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine)
        }
    }
    finally {
        foreach ($path in @($stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            }
        }
    }
}


function Repair-FetchHead {
    param([string]$RepositoryRoot)

    $gitDirectory = Join-Path $RepositoryRoot '.git'
    $paths = @(
        (Join-Path $gitDirectory 'FETCH_HEAD.lock'),
        (Join-Path $gitDirectory 'FETCH_HEAD')
    )

    foreach ($path in $paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }

        & attrib -R -S -H $path 2>$null | Out-Null
        Remove-Item -LiteralPath $path -Force -ErrorAction Stop
    }
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
    $fetchResult = Invoke-GitCommand -Arguments @('fetch', $Remote, $Branch)
    if (($fetchResult.ExitCode -ne 0) -and ($fetchResult.Output -match "cannot open '.*FETCH_HEAD': Permission denied")) {
        Write-Host "Detected a stale FETCH_HEAD write failure. Retrying once after cleanup." -ForegroundColor Yellow
        Repair-FetchHead -RepositoryRoot $repoRoot
        $fetchResult = Invoke-GitCommand -Arguments @('fetch', $Remote, $Branch)
    }

    if ($fetchResult.ExitCode -ne 0) {
        throw "git fetch $Remote $Branch failed with exit code $($fetchResult.ExitCode)."
    }

    $mergeResult = Invoke-GitCommand -Arguments @('merge', '--ff-only', "$Remote/$Branch")
    if ($mergeResult.ExitCode -ne 0) {
        throw "git merge --ff-only $Remote/$Branch failed with exit code $($mergeResult.ExitCode)."
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