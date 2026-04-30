@echo off
:: ============================================================
:: SR Payroll — Deploy & Update
:: Dubbelklik dit bestand om de laatste staging-code te pullen
:: en Odoo te herstarten.
::
:: Voer uit als Administrator (rechtsklik → Als administrator uitvoeren)
:: ============================================================

setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%deploy_update.ps1"

echo.
echo  SR Payroll — Deploy Update
echo  ===========================
echo  Branch : staging
echo  Actie  : pull + Odoo herstart
echo.

:: Controleer of het PowerShell-script bestaat
if not exist "%PS_SCRIPT%" (
    echo  [FOUT] deploy_update.ps1 niet gevonden naast dit bestand.
    echo  Zorg dat beide bestanden in dezelfde map staan.
    pause
    exit /b 1
)

:: Voer het PowerShell-script uit met omzeiling van de ExecutionPolicy
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*

set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE% neq 0 (
    echo.
    echo  [FOUT] Deploy mislukt met code %EXIT_CODE%.
    echo  Bekijk de foutmelding hierboven.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo  Druk op een toets om dit venster te sluiten...
pause > nul
endlocal
