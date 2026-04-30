@echo off
:: ============================================================
:: SR Payroll -- Testsuite uitvoeren
::
:: Dubbelklik dit bestand (als Administrator) om alle
:: l10n_sr_hr_payroll tests te draaien.
::
:: Het resultaat verschijnt in dit venster en wordt
:: opgeslagen als logbestand op het bureaublad.
:: ============================================================

setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%run_tests.ps1"

echo.
echo  SR Payroll -- Testsuite
echo  =======================
echo  Module   : l10n_sr_hr_payroll
echo  Database : Salarisverwerking-Module
echo  Log      : Bureaublad (odoo_test_*.log)
echo.
echo  Let op: Odoo wordt tijdelijk gestopt tijdens de tests.
echo          Dit duurt 2 tot 5 minuten.
echo.

if not exist "%PS_SCRIPT%" (
    echo  [FOUT] run_tests.ps1 niet gevonden naast dit bestand.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*

set "EXIT_CODE=%ERRORLEVEL%"

echo.
if %EXIT_CODE% equ 0 (
    echo  Resultaat: GESLAAGD
) else (
    echo  Resultaat: MISLUKT (code %EXIT_CODE%) -- bekijk het logbestand op het bureaublad.
)
echo.
echo  Druk op een toets om dit venster te sluiten...
pause > nul

endlocal
exit /b %EXIT_CODE%
