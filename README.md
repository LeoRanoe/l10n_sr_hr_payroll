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
