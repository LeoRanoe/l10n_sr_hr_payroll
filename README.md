# l10n_sr_hr_payroll

Suriname payroll add-on voor Odoo 18, afgestemd op de payrollcontext in `Salarisverwerking Module/Loonbelasting context.md`.

## Wat de module doet

De module ondersteunt:

- Artikel 14 loonbelasting via bewerkbare `hr.rule.parameter` records
- maandloon en fortnight-verloning (`12` of `26` periodes)
- FN 2026 tijdvakvalidatie en indicatoren
- AOV-berekening met parametergestuurd tarief en franchise
- overwerk (Art. 17c)
- bijzondere beloningen (Art. 17)
- uitkering ineens / jubileum (Art. 17a)
- contractweergave, loonstrookrapport en configuratie/help-pagina's
- multi-currency payroll met SRD-, USD- en EUR-ondersteuning
- FX-lock per loonstrook voor historische koersvastheid
- exporteerbaar fiscaal overzicht op basis van een live SQL-view

## Release Note 18.0.1.0

Deze release levert de definitieve Suriname Payroll v1.0 voor Odoo 18.

- Multi-Currency Engine: contracten en loonstroken ondersteunen SRD, USD en EUR met een bevroren koerssnapshot per loonstrook.
- FX-Lock & Audit Trail: bevestigde SR-loonstroken bewaren contractvaluta, wisselkoers, netto bronvaluta en belastingvrije voet voor reproduceerbare fiscale controles.
- Exportable Fiscal Reports: het fiscaal overzicht draait op een live PostgreSQL SQL-view met filtering per loonrun, afdeling, contractvaluta en bedrijf.
- Release Hardening: standaard 2026-parameters worden bij installatie geladen, wisselkoersen zijn strikt positief gevalideerd en multi-company record rules beschermen de rapportage.

## Belangrijke functionele keuze

De Art. 14 engine volgt de formulelijn uit `Loonbelasting context.md`.
Dat betekent dat de module momenteel **geen actieve heffingskorting** toepast in de wettelijke LB-berekening.

## Parameterbeheer

Alle belangrijke fiscale waarden zijn bewerkbaar via:

`Payroll -> Configuratie -> Suriname -> SR Payroll Instellingen`

De contractbron voor 2026 zit in:

`Contract -> Suriname Payroll -> Fiscale Data`

De migratiestappen voor bestaande klanten staan in:

`MIGRATION_GUIDE_2025_TO_2026.md`

De reguliere Art. 14 schijven zijn uitbreidbaar via codes zoals:

- `SR_SCHIJF_1_GRENS`, `SR_SCHIJF_2_GRENS`, ...
- `SR_TARIEF_1`, `SR_TARIEF_2`, ...

Reserve-parameters voor toekomstige uitbreiding zijn al aanwezig, onder andere:

- `SR_SCHIJF_4_GRENS`
- `SR_TARIEF_5`

Zonder actieve parameterwaarde beïnvloeden die placeholders de huidige berekening niet.

## Installatie en automatisering

### Test-VM setup vanaf `origin/staging`

Voor een test-VM is de veiligste flow:

1. zorg dat `git` beschikbaar is op de VM
2. zorg dat PostgreSQL op de VM is geinstalleerd en bereikbaar is op de host/poort uit `server/odoo.conf`
2. gebruik een aparte testdatabase
3. laat de modulecode altijd syncen vanaf alleen `origin/staging`
4. draai daarna een Odoo `install` of `update` headless met `--stop-after-init`

Als PostgreSQL ontbreekt op de VM, stopt `sync_from_staging.ps1` nu vroeg met een duidelijke prereq-fout in plaats van pas later met een Odoo stacktrace.

Voor Windows is daar nu een wrapper voor:

`scripts/sync_from_staging.ps1`

Voor een volledigere test-VM bootstrap is er nu ook:

`scripts/bootstrap_test_vm.ps1`

Dat script automatiseert extra stappen rond een nieuwe VM:

- installeert Git via `winget` als `git` nog ontbreekt
- probeert PostgreSQL eerst via `winget` te installeren en valt daarna terug op een directe download van de officiële installer als `winget` op de VM een 403-downloadfout geeft
- start de PostgreSQL service
- leest `db_host`, `db_port`, `db_user` en `db_password` uit `server/odoo.conf`
- maakt of herstelt automatisch de Odoo database-role in PostgreSQL met `CREATEDB`
- roept daarna `scripts/sync_from_staging.ps1` aan om de module vanaf alleen `origin/staging` te installeren en optioneel een Scheduled Task te registreren

Het script doet dit in vaste volgorde:

- clone of update van de repo vanaf alleen `origin/staging`
- checkout naar lokale branch `staging`
- fast-forward pull vanaf `origin/staging`
- optioneel afdwingen van een schone worktree met `-ForceClean`
- Odoo module `install` of `update` via het bestaande `scripts/install_module.py`
- automatische `--data-dir` onder `%TEMP%`, zodat tijdelijke test-runs niet vastlopen op schrijfrechten onder `Program Files`
- optionele Windows Scheduled Task die periodiek op nieuwe commits controleert en alleen dan een Odoo update uitvoert

Belangrijk: deze automation doet bewust een headless Odoo-run met `--stop-after-init --no-http`. Dat betekent dat de module wel wordt geïnstalleerd of geüpdatet, maar dat er daarna geen blijvende webserver op `http://localhost:8069` draait.

Start Odoo daarna apart, bijvoorbeeld zo:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
..\python\python.exe .\odoo-bin -c .\odoo.conf -d sr_payroll_test
```

#### Lokale login repareren op Windows

Als Odoo lokaal wel draait maar de loginpagina blijft hangen op `Wrong login/password`, gebruik dan:

`scripts/fix_local_login.ps1`

Snelste optie zonder de lange PowerShell-oproep:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0\l10n_sr_hr_payroll"
.\scripts\fix_local_login.cmd
```

Die wrapper gebruikt de bekende lokale standaardwaarden en opent direct een private browser-window.
Als Git beschikbaar is, probeert die wrapper eerst automatisch `origin/staging` fast-forward binnen te halen voordat het login-script start.

Als je expliciet eerst Git wilt pullen en daarna pas de login-fix wilt runnen, gebruik dan:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0\l10n_sr_hr_payroll"
.\scripts\pull_staging_and_fix_login.cmd
```

Die launcher doet altijd eerst `git fetch origin staging` en daarna `git pull --ff-only origin staging`.

Als je liever een native PowerShell-script gebruikt in plaats van een `.cmd` launcher, gebruik dan:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0\l10n_sr_hr_payroll"
.\scripts\pull_staging_and_fix_login.ps1
```

Dat PowerShell-script doet hetzelfde: eerst `git fetch origin staging`, daarna `git merge --ff-only origin/staging`, en daarna `fix_local_login.ps1` met de bekende standaardwaarden.
Bij een tijdelijke Windows-fout op `.git\FETCH_HEAD` probeert die wrapper eerst het bestand op te schonen en daarna de Git-sync nog één keer opnieuw.

Voorbeeld:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0\l10n_sr_hr_payroll"
.\scripts\fix_local_login.ps1 `
	-OdooRoot "C:\Program Files\Odoo 18.0e.20260407" `
	-Database "Salarisverwerking-Module" `
	-Login "stagiaire2.rpbg@gmail.com" `
	-TemporaryPassword "Welkom1234" `
	-OpenInPrivate
```

Dit script:

- leest automatisch `server\odoo.conf`
- controleert of de gekozen database bestaat
- valt automatisch terug op de enige gevonden niet-systeemdatabase als de opgegeven naam niet bestaat
- reset het gekozen Odoo-loginwachtwoord naar een bekende tijdelijke waarde
- valideert die login direct via een echte HTTP-aanroep naar `/web/login`
- opent optioneel de juiste login-URL in een private browser-window

Dit is los van de Odoo Enterprise product key. Een ontbrekende licentie kan wel banners of vervalwaarschuwingen tonen, maar veroorzaakt niet zelf `Wrong login/password` op een lokaal geverifieerde login.

#### Eenmalige installatie met alleen plakken in PowerShell

Als deze bestanden al naar `origin/staging` zijn gepusht, kun je op een schone test-VM dit plakken in een verhoogde PowerShell:

```powershell
$scriptUrl = "https://raw.githubusercontent.com/LeoRanoe/l10n_sr_hr_payroll/staging/scripts/bootstrap_test_vm.ps1"
$localScript = Join-Path $env:TEMP "bootstrap_test_vm.ps1"
Invoke-WebRequest -UseBasicParsing -Uri $scriptUrl -OutFile $localScript

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $localScript `
	-OdooRoot "C:\Program Files\Odoo 18.0e.20260407" `
	-AddonsRoot "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0" `
	-Database "sr_payroll_test" `
	-RegisterScheduledTask `
	-CheckEveryMinutes 15
```

Belangrijk bij een lege VM zonder PostgreSQL:

- het bootstrap-script probeert PostgreSQL eerst via `winget --interactive`
- als `winget` de installer niet kan downloaden, downloadt het script dezelfde PostgreSQL installer direct en start die alsnog interactief
- het script vraagt zelf om de PostgreSQL admin-password voordat het de Odoo-role aanmaakt
- die PostgreSQL admin-password is niet hetzelfde als `db_password` uit `odoo.conf`; `db_password` hoort bij Odoo gebruiker `openpg`
- gebruik in de PostgreSQL installer wizard dezelfde admin-password als je in die prompt invult
- daarna kan het script automatisch de Odoo-role uit `odoo.conf` aanmaken en de module-installatie afmaken

Als de bootstrap meldt `password authentication failed for user "postgres"`, dan betekent dat meestal een van deze twee dingen:

1. je hebt niet de PostgreSQL superuser-password ingevoerd die je tijdens de installer koos
2. jouw PostgreSQL superuser heet niet `postgres`

In dat tweede geval kun je de bootstrap opnieuw draaien met bijvoorbeeld:

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $localScript `
	-OdooRoot "C:\Program Files\Odoo 18.0e.20260407" `
	-AddonsRoot "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0" `
	-Database "sr_payroll_test" `
	-PostgreSqlInstallerPath "C:\Temp\PostgreSQL 16_16.13-3_Machine_X64_exe_en-US.exe" `
	-PostgreSqlAdminUser "jouw_admin_user" `
	-RegisterScheduledTask `
	-CheckEveryMinutes 15
```

#### Als de VM ook de directe PostgreSQL download blokkeert

Sommige VM's of netwerken blokkeren `https://get.enterprisedb.com/...` volledig. In dat geval:

1. download de PostgreSQL installer op een andere machine die wel toegang heeft
2. kopieer die `.exe` naar de VM, bijvoorbeeld naar `C:\Temp\postgresql-16.13-3-windows-x64.exe`
3. draai daarna hetzelfde bootstrap-script, maar geef het lokale installerpad mee

Voorbeeld:

```powershell
$scriptUrl = "https://raw.githubusercontent.com/LeoRanoe/l10n_sr_hr_payroll/staging/scripts/bootstrap_test_vm.ps1"
$localScript = Join-Path $env:TEMP "bootstrap_test_vm.ps1"
Invoke-WebRequest -UseBasicParsing -Uri $scriptUrl -OutFile $localScript

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $localScript `
	-OdooRoot "C:\Program Files\Odoo 18.0e.20260407" `
	-AddonsRoot "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0" `
	-Database "sr_payroll_test" `
	-PostgreSqlInstallerPath "C:\Temp\postgresql-16.13-3-windows-x64.exe" `
	-RegisterScheduledTask `
	-CheckEveryMinutes 15
```

Je kunt ook een alternatieve interne mirror of fileserver-URL meegeven met `-PostgreSqlInstallerUrl` als jouw organisatie de installer elders host.

Als PostgreSQL al op de VM staat, loopt het script direct door naar role-setup en module-installatie.

#### Als je de PostgreSQL superuser-password niet weet

Voor een geïsoleerde test-VM kun je ook een volledig geautomatiseerde fallback gebruiken die tijdelijk alleen voor localhost `trust` toevoegt in `pg_hba.conf`, PostgreSQL herstart, de Odoo-role aanmaakt en daarna de originele auth-config direct terugzet.

Gebruik dit alleen op een afgesloten test-VM waar jij beheerder bent.

Voorbeeld:

```powershell
$scriptUrl = "https://raw.githubusercontent.com/LeoRanoe/l10n_sr_hr_payroll/staging/scripts/bootstrap_test_vm.ps1"
$localScript = Join-Path $env:TEMP "bootstrap_test_vm.ps1"
Invoke-WebRequest -UseBasicParsing -Uri $scriptUrl -OutFile $localScript

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $localScript `
	-OdooRoot "C:\Program Files\Odoo 18.0e.20260407" `
	-AddonsRoot "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0" `
	-Database "sr_payroll_test" `
	-PostgreSqlInstallerPath "C:\Temp\PostgreSQL 16_16.13-3_Machine_X64_exe_en-US.exe" `
	-UseTemporaryLocalTrustBootstrap `
	-RegisterScheduledTask `
	-CheckEveryMinutes 15
```

Met deze optie hoef je geen PostgreSQL superuser-password in te voeren. Het script gebruikt dan alleen tijdelijk lokale trust-authenticatie om gebruiker `openpg` met het wachtwoord uit `odoo.conf` aan te maken of bij te werken.

#### Alleen de staging-wrapper zonder PostgreSQL bootstrap

Als Git en PostgreSQL al correct aanwezig zijn op de VM, kun je ook alleen de staging-wrapper gebruiken:

```powershell
$scriptUrl = "https://raw.githubusercontent.com/LeoRanoe/l10n_sr_hr_payroll/staging/scripts/sync_from_staging.ps1"
$localScript = Join-Path $env:TEMP "sync_from_staging.ps1"
Invoke-WebRequest -UseBasicParsing -Uri $scriptUrl -OutFile $localScript

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $localScript `
	-AddonsRoot "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0" `
	-OdooRoot "C:\Program Files\Odoo 18.0e.20260407" `
	-Database "sr_payroll_test" `
	-Action install `
	-RegisterScheduledTask `
	-CheckEveryMinutes 15
```

Wat dit precies doet:

- downloadt alleen de bootstrap-wrapper
- cloned de module naar de addons-map als die nog ontbreekt
- forceert lokale branch `staging` met remote `origin/staging`
- voert een headless Odoo installatie uit op database `sr_payroll_test`
- registreert een Scheduled Task die elke 15 minuten nieuwe commits op `origin/staging` zoekt

#### Handmatige update-run vanaf de repo op de VM

Als de repo al op de VM staat:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0\l10n_sr_hr_payroll"
.\scripts\sync_from_staging.ps1 `
	-Database "sr_payroll_test" `
	-Action update
```

Die update-run doet alleen een Odoo `-u l10n_sr_hr_payroll` als er echt nieuwe commits op `origin/staging` zijn binnengekomen.

#### Force-clean voor strikt testgebruik

Als je op de VM nooit lokale handmatige wijzigingen bewaart, kun je updates volledig branch-gestuurd maken:

```powershell
.\scripts\sync_from_staging.ps1 `
	-Database "sr_payroll_test" `
	-Action update `
	-ForceClean
```

Gebruik `-ForceClean` alleen op een test-VM, want lokale niet-gecommitte wijzigingen in de modulemap worden dan verwijderd.

#### Scheduled Task opnieuw aanmaken of wijzigen

Dit registreert of overschrijft de updater-taak opnieuw:

```powershell
.\scripts\sync_from_staging.ps1 `
	-Database "sr_payroll_test" `
	-Action update `
	-RegisterScheduledTask `
	-CheckEveryMinutes 15
```

De taak draait als `SYSTEM`, dus voer dit uit in een verhoogde PowerShell. Dat is bewust gekozen zodat de taak ook zonder ingelogde gebruiker kan blijven updaten.

De wrapper ondersteunt bewust geen branch-override. Elke run haalt alleen code op uit `origin/staging`.

### Databasegedrag bij installatie

Ja. Een installatie of update van `l10n_sr_hr_payroll` wijzigt de database.
Dat is normaal voor Odoo-modules, omdat Odoo tijdens `-i` of `-u` onder andere:

- tabellen en kolommen aanmaakt of bijwerkt voor Python-modellen
- XML-data laadt of herschrijft voor loonregels, parameters, views en security
- metadata bijwerkt in `ir.model.data`, `ir.ui.view`, `ir.config_parameter` en verwante tabellen

Het besturingssysteem verandert dat gedrag niet. Op Windows en Linux krijg je dezelfde database-impact zolang je dezelfde Odoo-versie, dezelfde afhankelijkheden en dezelfde modulecode gebruikt.

Voor geautomatiseerd testen is daarom de veiligste aanpak:

1. gebruik een aparte testdatabase
2. draai een schone `install` op een lege of nieuwe database
3. draai daarnaast ook een `update` op een bestaande kopie als je upgradepaden wilt bewaken

### Geautomatiseerde installatie

Deze module bevat nu een cross-platform script:

`scripts/install_module.py`

Het script:

- detecteert in deze workspace automatisch `server/odoo-bin` en `server/odoo.conf`
- gebruikt op Windows automatisch de bundled `python/python.exe`
- draait standaard headless met `--stop-after-init`, `--no-http` en `--without-demo=all`
- ondersteunt zowel een schone installatie (`--action install`) als een update-run (`--action update`)
- kan direct tests meedraaien met `--test-enable`

Voorwaarden:

1. `l10n_sr_hr_payroll` staat al in het Odoo `addons_path`
2. de doel-database bestaat al, of jouw Odoo/PostgreSQL-configuratie mag die database aanmaken
3. `hr_payroll` is beschikbaar in dezelfde Odoo-installatie

#### Windows

Schone installatierun op een testdatabase:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0\l10n_sr_hr_payroll"
& "C:\Program Files\Odoo 18.0e.20260407\python\python.exe" .\scripts\install_module.py `
	--database "sr_payroll_ci_clean" `
	--action install `
	--test-enable
```

Update-run op een bestaande database:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\sessions\addons\18.0\l10n_sr_hr_payroll"
& "C:\Program Files\Odoo 18.0e.20260407\python\python.exe" .\scripts\install_module.py `
	--database "Salarisverwerking-Module" `
	--action update `
	--test-enable
```

#### Linux

Als je Linux-layout dezelfde structuur heeft als deze workspace, detecteert het script Odoo meestal automatisch. Als dat niet zo is, geef dan expliciet `--odoo-bin` en `--config` mee.

Schone installatierun op een testdatabase:

```bash
cd /opt/odoo/sessions/addons/18.0/l10n_sr_hr_payroll
python3 scripts/install_module.py \
	--database sr_payroll_ci_clean \
	--action install \
	--test-enable \
	--odoo-bin /opt/odoo/server/odoo-bin \
	--config /opt/odoo/server/odoo.conf
```

Update-run op een bestaande database:

```bash
cd /opt/odoo/sessions/addons/18.0/l10n_sr_hr_payroll
python3 scripts/install_module.py \
	--database salarisverwerking_module \
	--action update \
	--test-enable \
	--odoo-bin /opt/odoo/server/odoo-bin \
	--config /opt/odoo/server/odoo.conf
```

#### Aanbevolen automatische testflow

Als je grote wijzigingen maakt, is een enkele update-run niet genoeg. Gebruik in je VM of pipeline minimaal deze twee stappen:

1. `install` op een schone database om fresh-install fouten te vinden
2. `update` op een bestaande databasekopie om migratie- of upgradefouten te vinden

Optionele extra Odoo-argumenten kun je doorgeven met herhaalde `--extra-arg` parameters.

Voorbeeld:

```powershell
& "C:\Program Files\Odoo 18.0e.20260407\python\python.exe" .\scripts\install_module.py `
	--database "sr_payroll_ci_clean" `
	--action install `
	--test-enable `
	--extra-arg=--log-handler=:INFO
```

## Validatie

Voor deze module is de betrouwbaarste non-interactieve validatie een update of install met `--test-enable` en `--stop-after-init`.

Handmatige referentie-opdracht vanaf de Odoo server-root:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
& "C:\Program Files\Odoo 18.0e.20260407\python\python.exe" .\odoo-bin -u l10n_sr_hr_payroll --test-enable -d "Salarisverwerking-Module" --stop-after-init --no-http --log-level=test
```

## Belangrijkste bestanden

- `__manifest__.py`
- `models/hr_contract.py`
- `models/hr_payslip.py`
- `models/sr_artikel14_calculator.py`
- `data/hr_rule_parameter_data.xml`
- `data/hr_salary_rule_data.xml`
- `reports/report_payslip_sr.xml`
- `views/hr_contract_views.xml`
- `views/hr_payroll_config_sr_views.xml`
- `views/sr_help_template.xml`
- `tests/test_article_14.py`
- `tests/test_article_14_integration.py`

## Licentie

De module declareert `LGPL-3` in het manifest.
