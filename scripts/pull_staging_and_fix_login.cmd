@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

git --version >nul 2>nul
if errorlevel 1 (
	echo [error] Git is not available in PATH.
	endlocal & exit /b 1
)

if not exist "%REPO_ROOT%\.git" (
	echo [error] Could not find the Git repository at "%REPO_ROOT%".
	endlocal & exit /b 1
)

pushd "%REPO_ROOT%" >nul
git fetch origin staging
if errorlevel 1 (
	set "EXIT_CODE=%ERRORLEVEL%"
	popd >nul
	endlocal & exit /b %EXIT_CODE%
)

git pull --ff-only origin staging
if errorlevel 1 (
	set "EXIT_CODE=%ERRORLEVEL%"
	popd >nul
	endlocal & exit /b %EXIT_CODE%
)
popd >nul

if "%~1"=="" (
	"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%fix_local_login.ps1" -OpenInPrivate
) else (
	"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%fix_local_login.ps1" %*
)
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%