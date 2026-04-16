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
- contractpreview, loonstrookrapport en configuratie/help-pagina's

## Belangrijke functionele keuze

De Art. 14 engine volgt de formulelijn uit `Loonbelasting context.md`.
Dat betekent dat de module momenteel **geen actieve heffingskorting** toepast in de wettelijke LB-berekening.

## Parameterbeheer

Alle belangrijke fiscale waarden zijn bewerkbaar via:

`Payroll -> Configuratie -> Suriname -> SR Belastingparameters`

De reguliere Art. 14 schijven zijn uitbreidbaar via codes zoals:

- `SR_SCHIJF_1_GRENS`, `SR_SCHIJF_2_GRENS`, ...
- `SR_TARIEF_1`, `SR_TARIEF_2`, ...

Reserve-parameters voor toekomstige uitbreiding zijn al aanwezig, onder andere:

- `SR_SCHIJF_4_GRENS`
- `SR_TARIEF_5`

Zonder actieve parameterwaarde beïnvloeden die placeholders de huidige berekening niet.

## Installatie

1. Plaats `l10n_sr_hr_payroll` in het Odoo addons-pad.
2. Herstart de Odoo-server.
3. Update de apps-lijst.
4. Installeer of update de module.

Voorbeeld:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
.\odoo-bin -u l10n_sr_hr_payroll -d "Salarisverwerking-Module" --stop-after-init
```

## Validatie

De release-validatie voor deze module is uitgevoerd met:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
.\odoo-bin -u l10n_sr_hr_payroll --test-enable -d "Salarisverwerking-Module" --stop-after-init --log-level=test --workers=0
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
