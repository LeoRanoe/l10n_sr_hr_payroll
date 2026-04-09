# l10n_sr_hr_payroll

Korte beschrijving
------------------
Een Odoo-add-on voor HR / salarisfunctionaliteit (module: `l10n_sr_hr_payroll`). Dit project bevat modeldefinities, salarisregels, rapporten en tests voor gebruik binnen een Odoo-installatie.

Belangrijkste bestanden
----------------------
- `__manifest__.py` - module manifest
- `models/hr_contract.py` - contractmodel en bedrijfslogica
- `reports/report_payslip_sr.xml` - payslip-rapport
- `views/hr_contract_views.xml` - view-definities
- `tests/test_article_14.py` - automatische tests

Branches
--------
Deze repository gebruikt de volgende branches:
- `main` — stabiele, productieklare code
- `staging` — pre-productie integratie
- `dev` — actieve ontwikkeling, feature-branches

Installatie (kort)
------------------
1. Plaats de map `l10n_sr_hr_payroll` in je Odoo `addons`-pad (bijv. `C:\Program Files\Odoo\addons` of je custom addons map).
2. Herstart de Odoo-server.
3. Update de apps-lijst en installeer de module `l10n_sr_hr_payroll` via de Odoo UI of CLI.

Voorbeeld (CLI):
```powershell
# Pas paden aan naar jouw omgeving
python odoo-bin --addons-path="/pad/naar/addons;./" -d test_db --test-enable --stop-after-init -i l10n_sr_hr_payroll
```

Ontwikkelen en testen
----------------------
- Gebruik een eigen ontwikkelbranch van `dev` voor features en maak pull requests naar `staging`.
- Tests in `tests/` zijn bedoeld om met de Odoo test-runner uitgevoerd te worden (zie voorbeeld hierboven).

Contributie
-----------
1. Fork de repository.
2. Maak een feature-branch van `dev`.
3. Open een pull request naar `staging` met een duidelijke beschrijving.

Licentie
--------
Er is momenteel geen expliciet `LICENSE`-bestand in deze repository. Voeg een licentie toe of controleer met de repository-eigenaar welke licence van toepassing is.

Contact
-------
Open een issue in de repository of contacteer de maintainer voor vragen.

---
Engelse samenvatting
--------------------
Short README with install and development notes for the `l10n_sr_hr_payroll` Odoo addon.
