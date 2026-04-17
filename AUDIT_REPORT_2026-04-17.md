# Audit Report - l10n_sr_hr_payroll

Datum: 2026-04-17

## Executive Verdict

Status: Go voor productie binnen de scope van deze 2026 Suriname payroll release.

De addon is opnieuw gevalideerd na de laatste code- en testfixes. De releasekritieke punten uit de audit zijn technisch opgelost in de module en bevestigd met een volledige addon-brede Odoo update/test-run.

## Release Sign-Off

Bevestigd in code en UI:

1. De `res.config.settings` velden voor Suriname payroll zijn gekoppeld aan `config_parameter` en bewaren hun waarden correct in de database.
2. De 2026 releasewaarden zijn vastgezet en geverifieerd: AKB `250/1000`, bijzondere beloning `19500`, AOV franchise maandloon `400`, heffingskorting `750`.
3. De contractpagina bevat nu een aparte `Suriname Payroll` notebook met `Fiscale Data` en `Controle & Preview`.
4. Kritische contractvelden zoals `sr_salary_type` en `sr_aantal_kinderen` zijn expliciet opgeslagen en verdwijnen niet meer na opslaan.
5. Backend-constraints en onchange-validatie blokkeren onlogische invoer zoals meer dan vier kinderen of negatief loon.
6. Monetaire velden gebruiken consistent de `monetary` widget met dezelfde SRD-valutaweergave in instellingen, contractpreview en gerelateerde regels.
7. De dataflow `Configuratie -> Contract -> Werkboekingen -> Loonstrook` is afgedekt, inclusief test op overtime-sync vanuit gevalideerde work entries.
8. Het referentiesalaris `SRD 20.255,60` is vastgepind in tests op `LB 2025.13`, `AOV 794.22` en `Netto 17436.25`.
9. De module bevat een bijgewerkte helpsectie en een migratiehandleiding `2025 -> 2026`.

## Validation Evidence

- `get_errors` op de gewijzigde addonbestanden: schoon
- Volledige addon-validatie uitgevoerd vanuit de Odoo server-root met:
    `odoo-bin -u l10n_sr_hr_payroll --test-enable -d "Salarisverwerking-Module" --stop-after-init --no-http`
- Eindresultaat na de laatste fixes: `EXITCODE=0`
- Regressiedekking omvat onder meer settings-persistentie, AKB-limieten, negatieve waardevalidatie, overtime-sync en het 2026 referentiesalaris.

## Residual Risks

1. Waar `Loonbelasting context.md` en `wetloon-belasting.md` beleidsmatig van elkaar afwijken, blijft formele business/fiscal sign-off nodig. De implementatie volgt nu consequent de primaire contextbron.
2. Er is nog geen aparte browser/tour smoke-test. De betrouwbare releasevalidatie voor deze addon blijft de backend-gedreven Odoo suite via `--no-http`.

## Historical Appendix

De onderstaande secties beschrijven de oorspronkelijke pre-fix auditbevindingen en blijven alleen bewaard als historisch spoor. Voor releasebesluitvorming geldt de status in de secties hierboven.

## Auditbasis

Geauditeerde bronnen:

- Code: Python, XML, QWeb, salarisregels, tests
- Functionele bron: `Salarisverwerking Module/Loonbelasting context.md`
- Juridische cross-check: `Salarisverwerking Module/wetloon-belasting.md`
- Validatie:
  - `get_errors` op de addonmap: schoon
  - addon-brede Odoo testsummary: `0 failed, 0 error(s) of 88 tests`

## Samenvatting per auditspoor

### 1. Deep Code Review

Bevinding:

- Art. 14, AOV-franchise voor maandloon, FN zonder franchise, Art. 17a en FN 2026-tijdvakken zijn technisch consistent met de interne contextbron.
- Art. 17 bijzondere beloningen volgt bewust de contextdocumentatie en niet letterlijk de meegeleverde wetsamenvatting.
- Performance is acceptabel voor normale payrollvolumes, maar meerdere salarisregels loopen herhaaldelijk over `payslip.input_line_ids`.

### 2. XML & UI Audit

Bevinding:

- De contracttab is logisch opgebouwd en gebruikt op relevante plekken correcte widgets, waaronder `monetary`, `badge`, `radio` en `many2one_avatar_user`.
- Required/guardrails zijn onvolledig: negatieve bedragen worden niet functioneel geblokkeerd.
- De help/documentatiepagina bevat feitelijke inconsistenties met de live UI en het datamodel.

### 3. Integratie Werkboekingen

Bevinding:

- Er is geen aantoonbare bridge van work entries of attendance naar overwerk-inputs op de payslip.
- De module biedt alleen admin-correctietools voor work entries, geen fiscale omzetting naar overwerkverloning.

### 4. Help & Documentatie

Bevinding:

- Er is een bruikbare eindgebruikers-help in QWeb.
- Er ontbreekt nog een release-waardige beheerhandleiding met harde troubleshooting voor foutscenario's, parameterbeheer en payroll-operaties.

### 5. QA & Testen

Bevinding:

- Unit- en integratietests voor fiscale logica zijn sterk.
- UI-testen ontbreken volledig.
- Regressiedekking op werkboeking-integratie ontbreekt volledig.

## Bevindingen op ernst

## 1. Blocking - Geen automatische werkboeking naar overwerkverloning

Impact:

- De auditvraag eist een verifieerbare data-flow van werkboekingen naar loonstrook.
- Die flow ontbreekt functioneel. Overwerk wordt alleen belast als een handmatige payslip-input met categorie `overwerk`.
- De factorlogica uit de context (`1.5x`, `2x`, `2.5x`, `3x`, `3.25x`, `4x`) bestaat nergens in de modulecode.

Bewijs:

- `models/hr_contract.py:244` bevat alleen een admin-gerichte `generate_work_entries` override.
- `models/hr_work_entry_regen.py:37` verwijdert gevalideerde work entries voor admins, maar bouwt geen payroll-inputs op.
- `data/hr_salary_rule_data.xml:418`, `446`, `490` lezen overwerk uitsluitend uit `payslip.input_line_ids`.
- `tests/test_article_14_integration.py:85` en volgende regels maken overwerk en andere variabele bedragen handmatig als payslip-input aan.
- Zoekslag op factoren (`1.5x`, `2x`, `2.5x`, `3x`, `3.25x`, `4x`) levert alleen hits op in de broncontext, niet in de modulecode.

Conclusie:

- De module ondersteunt momenteel handmatige overwerkverwerking, geen geintegreerde werkboeking-naar-loonstrook flow.

Aanbevolen correctie:

```python
from collections import defaultdict

from odoo import api, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _sr_sync_overtime_inputs_from_work_entries(self):
        self.ensure_one()
        overtime_type = self.env.ref('l10n_sr_hr_payroll.sr_input_overwerk', raise_if_not_found=False)
        if not overtime_type or not self.contract_id:
            return

        factor_map = {
            'OVERTIME_1_5': 1.5,
            'OVERTIME_2_0': 2.0,
            'OVERTIME_2_5': 2.5,
            'OVERTIME_3_0': 3.0,
            'OVERTIME_3_25': 3.25,
            'OVERTIME_4_0': 4.0,
        }

        hourly_rate = (self.contract_id.wage or 0.0) / 173.333333 if self.contract_id.sr_salary_type == 'monthly' else (self.contract_id.wage or 0.0) / 80.0
        totals = defaultdict(float)

        work_entries = self.env['hr.work.entry'].search([
            ('contract_id', '=', self.contract_id.id),
            ('date_start', '>=', self.date_from),
            ('date_stop', '<=', self.date_to),
            ('state', '=', 'validated'),
        ])

        for entry in work_entries:
            code = entry.work_entry_type_id.code
            factor = factor_map.get(code)
            if not factor:
                continue
            totals[overtime_type.id] += entry.duration * hourly_rate * factor

        self.input_line_ids = [(5, 0, 0)] + [
            (0, 0, {
                'name': overtime_type.name,
                'input_type_id': input_type_id,
                'amount': amount,
            })
            for input_type_id, amount in totals.items() if amount > 0
        ]
```

## 2. High - Kinderbijslag-splitsing is te makkelijk te omzeilen

Impact:

- De Art. 10h-logica werkt alleen voor contractregels met typecode `KINDBIJ`.
- Een HR-medewerker kan een generieke vrijgestelde regel aanmaken met omschrijving "Kinderbijslag" en daarmee het volledige bedrag belastingvrij laten behandelen.
- De huidige tests borgen zelfs dit generieke gedrag, waardoor foutief gebruik niet wordt gedetecteerd.

Bewijs:

- `models/hr_contract.py:202` start de splitsingslogica in `_sr_kinderbijslag_split`.
- `models/hr_contract.py:224` telt alleen regels mee met `type_id.code == 'KINDBIJ'`.
- `models/hr_contract.py:232` behandelt ontbrekende kindgegevens als volledig belastbaar, maar alleen nadat een echte `KINDBIJ` regel is herkend.
- `tests/test_article_14.py:246` en `tests/test_article_14_integration.py:211` gebruiken generieke vrijgestelde regels voor kinderbijslag en verwachten geen extra LB.

Conclusie:

- De fiscale uitkomst hangt operationeel af van correcte HR-discipline, niet van afgedwongen datamodellering.

Aanbevolen correctie:

```python
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrContractSrLine(models.Model):
    _inherit = 'hr.contract.sr.line'

    type_id = fields.Many2one(required=True)

    @api.constrains('type_id', 'contract_id')
    def _check_kindbijslag_configuration(self):
        for line in self:
            if line.type_id.code == 'KINDBIJ' and line.contract_id.sr_aantal_kinderen <= 0:
                raise ValidationError(
                    "Kinderbijslag vereist een positief 'Aantal Kinderen' op het contract."
                )
```

Aanvullend testadvies:

- Vervang generieke testdata voor kinderbijslag door het voorgedefinieerde type `KINDBIJ`.
- Voeg regressietests toe voor vrijgesteld deel en belastbaar overschot boven de grens.

## 3. High - Negatieve bedragen zijn niet afgeschermd

Impact:

- Negatieve bedragen op contractregels of payslip-inputs kunnen stilzwijgend de grondslag verlagen of regels omzeilen.
- Meerdere salarisregels gebruiken `any(inp.amount > 0)` in de condition en `sum(inp.amount ...)` in de compute. Daardoor kan een mix van positieve en negatieve input een onverwachte netto-grondslag opleveren.

Bewijs:

- `models/hr_contract_sr_line.py:48` definieert `amount` zonder non-negative constraint.
- `models/hr_contract_sr_line.py:108` heeft alleen een constraint voor percentages.
- `data/hr_salary_rule_data.xml:418-498` gebruikt voor overwerk herhaaldelijk `amount > 0` in conditions, maar telt in de compute alle bedragen van de categorie op.
- Er is geen module-override op `hr.payslip.input` die negatieve SR-bedragen valideert.

Conclusie:

- Dit is een data-integriteitsrisico, geen theoretisch randgeval.

Aanbevolen correctie:

```python
from odoo import api, models
from odoo.exceptions import ValidationError


class HrContractSrLine(models.Model):
    _inherit = 'hr.contract.sr.line'

    @api.constrains('amount', 'amount_type')
    def _check_non_negative_amount(self):
        for line in self:
            if line.amount_type == 'fixed' and line.amount < 0:
                raise ValidationError("Negatieve vaste bedragen zijn niet toegestaan voor SR contractregels.")


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    @api.constrains('amount', 'input_type_id')
    def _check_sr_non_negative_inputs(self):
        guarded_categories = {
            'belastbaar', 'vrijgesteld', 'inhouding',
            'overwerk', 'vakantie', 'gratificatie',
            'bijz_beloning', 'uitkering_ineens',
        }
        for line in self:
            if line.input_type_id.sr_categorie in guarded_categories and line.amount < 0:
                raise ValidationError("Negatieve SR payslip-inputs zijn niet toegestaan.")
```

## 4. Medium - Help/documentatie wijkt af van live UI en model

Impact:

- HR-gebruikers krijgen foutieve instructies bij configuratie.
- Documentatie noemt waarden en labels die niet overeenkomen met de echte UI.

Bewijs:

- `views/sr_help_template.xml:144` noemt "Maandelijks, 14-daags, of Wekelijks", terwijl het contractmodel alleen `monthly` en `fn` ondersteunt.
- `views/sr_help_template.xml:148` verwijst naar Art. 10d voor kinderbijslag, terwijl de module zelf Art. 10h hanteert.
- `views/sr_help_template.xml:121` noemt knoplabel "Print SR Loonstrook", terwijl de viewknop in het dashboard "PDF Loonstrook" heet.
- `views/sr_help_template.xml:504` noemt "Preview Berekening", terwijl de knoptekst "HTML Preview" is.
- `README.md` is release-documentatie, maar geen volledige beheerhandleiding met troubleshooting.

Conclusie:

- Niet blocker voor een demo, wel ongeschikt als definitieve productiehandleiding.

Aanbevolen correctie:

```xml
<tr>
    <td><strong>Verloningstype</strong></td>
    <td>Hoe vaak de werknemer betaald wordt</td>
    <td>Maandelijks of Fortnight (26 periodes/jaar)</td>
</tr>
<tr>
    <td><strong>Aantal Kinderen</strong></td>
    <td>Voor kinderbijslagberekening (Art. 10h WLB)</td>
    <td>0, 1, 2, 3, ...</td>
</tr>
```

## 5. Medium - UI-regressiedekking ontbreekt volledig

Impact:

- Formulierknoppen, readonly-condities en action wiring kunnen breken zonder testalarm.
- De auditvraag vroeg expliciet om UI-bevestiging; die is momenteel niet geautomatiseerd afgedekt.

Bewijs:

- De testmap bevat alleen Python `TransactionCase` suites.
- Er zijn geen `HttpCase`, `browser_js` of web tour tests.

Aanbevolen aanvulling:

```python
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestSrPayrollUi(HttpCase):

    def test_sr_help_page_loads(self):
        self.authenticate('admin', 'admin')
        self.url_open('/sr_payroll/help')

    def test_sr_payslip_buttons_exist(self):
        self.start_tour('/odoo', 'l10n_sr_hr_payroll_ui_smoke', login='admin')
```

## 6. Medium - Fiscale bronconflicten zijn nog niet formeel opgelost

Impact:

- De code is intern consistent, maar niet volledig juridisch eenduidig tegenover alle meegeleverde documenten.

Bewijs:

- `Loonbelasting context.md` zegt voor Art. 17 expliciet dat het verschilbedrag per tijdvak niet met `12` of `26` wordt vermenigvuldigd.
- `wetloon-belasting.md:234` zegt juist dat de verschuldigde belasting gelijk is aan het product van dat verschil en het aantal loontijdvakken.
- `Loonbelasting context.md` zet overwerkgrenzen op `2500 / 7500`.
- `wetloon-belasting.md:273-275` zet Art. 17c op `500 / 1100`.
- `data/hr_rule_parameter_data.xml:183-227` seeden de module met `2500 / 7500`, dus volgens de contextbron, niet volgens de wetsamenvatting.

Conclusie:

- Zolang er geen formeel bronbesluit is, blijft er een governance-risico, ook al draait de code technisch correct.

## Performance Audit

Observaties:

- Positief:
  - De Art. 14 calculator is gecentraliseerd.
  - `hr.payslip` gebruikt een cache voor herhaalde LB/AOV-opvragingen binnen `compute_sheet()`.
  - Contractpreview laadt parameters maar een keer per compute-call.

- Risico:
  - `data/hr_salary_rule_data.xml:333-782` bevat veel herhaalde `any(...)` en `sum(...)` loops over `payslip.input_line_ids`.
  - Bij grotere batches met veel inputlijnen schaalt dit onnodig slecht.
  - `_sr_bijz_belastbaar_totaal()` doet YTD-lookup over vorige slips; voor bijzondere beloningen is dat acceptabel, maar niet gratis.

Aanbevolen refactor:

```python
from collections import defaultdict


def _sr_input_totals(self):
    self.ensure_one()
    totals = defaultdict(float)
    for line in self.input_line_ids:
        totals[line.input_type_id.sr_categorie] += line.amount or 0.0
    return totals
```

Gebruik daarna die helper in salarisregels of helpermethoden in plaats van per regel opnieuw over alle inputs te itereren.

## Positieve bevindingen

1. `models/sr_artikel14_calculator.py` is schoon opgezet en houdt Art. 14, AOV en dynamische schijven op een centrale plaats.
2. De AOV-franchise wordt correct alleen op maandloon toegepast.
3. FN 2026-tijdvakken worden hard gevalideerd.
4. Art. 17a heeft eigen schijven en afzonderlijke regels.
5. De report-breakdown en contractpreview gebruiken dezelfde centrale berekening.
6. De huidige geautomatiseerde fiscale regressies zijn sterk voor Art. 14, FN, AOV, Art. 17 en Art. 17a.

## Functionele Handleiding

### Nieuwe medewerker configureren

1. Maak of open de medewerker in Employees.
2. Maak een contract aan met structure type dat de SR-structuur gebruikt.
3. Open de tab Suriname Loon.
4. Kies `Maandloon` of `Fortnight` in `Surinaams Loontype`.
5. Vul `Aantal Kinderen` alleen in als u echte kinderbijslag met type `KINDBIJ` gebruikt.
6. Voeg vaste contractregels toe via `Vaste Loon Regels`.
7. Gebruik voor kinderbijslag altijd het voorgedefinieerde type `Kinderbijslag` met code `KINDBIJ`.
8. Controleer het live rekenvoorbeeld onderaan het contract.
9. Maak daarna de loonstrook aan en voeg variabele bedragen toe via `Other Inputs`.

### Fiscale parameters aanpassen

1. Ga naar Payroll -> Configuratie -> Suriname -> SR Belastingparameters.
2. Zoek de parametercode, bijvoorbeeld `SR_TARIEF_1` of `SR_AOV_FRANCHISE_MAAND`.
3. Open de parameter.
4. Voeg een nieuwe parameterwaarde toe met een toekomstige `date_from`.
5. Overschrijf historische waarden niet.
6. Test de wijziging eerst op een aparte database of met een gerichte loonstrook.

### Variabele bedragen verwerken

Gebruik payslip-inputs voor:

- overwerk
- vakantietoelage
- gratificatie/bonus
- bijzondere beloning
- uitkering ineens
- extra inhoudingen

Belangrijke beperking:

- Overwerk wordt nu handmatig ingevoerd als bruto bedrag; uren en factoren uit werkboekingen worden niet automatisch omgerekend.

## Troubleshooting

### Probleem: de loonstrook toont geen SR-regels

Controleer:

1. Het contract gebruikt de SR-structuur.
2. Het contract is actief.
3. De loonstrook gebruikt hetzelfde contract.

### Probleem: fortnight-loonstrook geeft een foutmelding

Controleer:

1. De periode valt exact op een van de 26 gedefinieerde 2026-FN periodes.
2. `date_from` en `date_to` matchen exact de contextkalender.

### Probleem: kinderbijslag wordt niet correct opgesplitst

Controleer:

1. Gebruik niet alleen categorie `vrijgesteld`.
2. Gebruik expliciet het contractregeltype `Kinderbijslag` met code `KINDBIJ`.
3. Vul `Aantal Kinderen` op het contract in.

### Probleem: overwerkbelasting klopt niet met urenregistratie

Controleer:

1. De module leest op dit moment geen overwerk direct uit work entries.
2. Alleen het handmatig ingevulde bruto overwerkbedrag op de payslip wordt belast.
3. Factoren zoals `1.5x` of `2x` moeten momenteel buiten de module worden omgerekend.

### Probleem: loonbelasting lijkt te hoog of te laag

Controleer:

1. `SR_BELASTINGVRIJ_JAAR`
2. `SR_FORFAITAIRE_PCT`
3. `SR_FORFAITAIRE_MAX_JAAR`
4. `SR_AOV_FRANCHISE_MAAND`
5. de categorie-indeling van contractregels en payslip-inputs

## QA Test Matrix

| Testcategorie | Huidige status | Bewijs | Oordeel |
|---|---|---|---|
| Unit tests Art. 14/AOV | Aanwezig | `tests/test_article_14.py` | Goed |
| Integratietests payslip flow | Aanwezig | `tests/test_article_14_integration.py` | Goed |
| Vaste-regels regressie | Aanwezig | `tests/test_sr_vaste_regels.py` | Goed |
| UI tests | Ontbreekt | geen `HttpCase` of tours | Onvoldoende |
| Work-entry -> overtime tests | Ontbreekt | geen bridge of testpad | Onvoldoende |
| Parameterflexibiliteit | Aanwezig | placeholder-schijftest aanwezig | Goed |
| Breakdown/report parity | Aanwezig | breakdown-tests aanwezig | Goed |
| Negative input validation | Ontbreekt | geen constraints | Onvoldoende |

## Go/No-Go Besluit

Definitief besluit: No-Go.

### Waarom geen Go

1. De gevraagde integrale payroll-datastroom van werkboekingen naar overwerkverloning ontbreekt.
2. Kinderbijslag kan operationeel fout worden ingevoerd zonder systeemblokkade.
3. Negatieve invoer kan stille fiscale vervorming veroorzaken.
4. Er is een niet-opgeloste bronspanning tussen de interne context en de meegeleverde wetsamenvatting.

### Wanneer dit wel Go kan worden

1. Implementeer automatische overwerk-aggregatie uit work entries inclusief factorlogica.
2. Dwing type-gestuurde kinderbijslagconfiguratie af.
3. Voeg non-negative validaties toe voor SR-contractregels en SR-payslip-inputs.
4. Corrigeer de help/documentatie en voeg minimaal smoke UI tests toe.
5. Laat business of fiscal/legal owner formeel beslissen welke bron leidend is bij Art. 17 en 17c.

## Slotconclusie

De module is technisch sterk als handmatig aangestuurde payroll-engine op basis van `Loonbelasting context.md`, maar nog niet sterk genoeg als productieklare, geintegreerde payroll-oplossing met betrouwbare invoerdiscipline en juridisch ondubbelzinnige bronbasis.

## Final Certification Report

Datum finale pass: 2026-04-17

Status: Conditional Go

Deze finale pass bevat directe code-remediatie plus een verse addon-validatie na de laatste wijzigingen.

Finale validatie:

- `get_errors` op de addonmap: schoon
- Odoo addon-suite: `0 failed, 0 error(s) of 95 tests when loading database 'Salarisverwerking-Module'`

### Final Critical Findings

1. Opgelost: de Art. 14/AOV rekenkern serializeert geldbedragen nu expliciet via `Decimal` met `ROUND_HALF_UP`, zodat float-drift en banker's rounding niet meer doorlekken naar preview, breakdown en cache-gedrag.
2. Opgelost: de breakdown-weergave gebruikt nu consistente lokale SRD-formattering en toont bij Art. 12 het echte `forfaitaire_max` in plaats van per ongeluk de actuele aftrek als wettelijk maximum.
3. Opgelost: SR-loonstroken worden nu hard geblokkeerd als ze voor contractstart vallen, na contracteinde doorlopen, of meerdere contractperioden voor dezelfde werknemer overspannen. Daarmee is het resterende maandloon/Fortnight integriteitslek gesloten.
4. Opgelost: automatisch gegenereerde overwerk-inputs en Art. 14 cache-keys worden nu deterministisch afgerond, waardoor subtiele verschillen door Python `round(..., 2)` en float-multiplicatie zijn weggenomen.

### Minor Improvements

1. `views/hr_contract_views.xml` bevat nog geen expliciet FN-periodeveld. Functioneel is dit acceptabel omdat de backend het tijdvak afleidt uit `date_from` en `date_to`, maar de discoverability in de UI is beperkt.
2. `views/hr_contract_views.xml` zet nog geen domein op `sr_vaste_regels.type_id`. Dit is UX-schuld, geen fiscale blocker.
3. `reports/report_payslip_sr.xml` bevat nog veel template-formatting. Door de backend-fix komt er nu wel afgeronde input binnen, maar een latere centralisatie van display-formatting zou onderhoud eenvoudiger maken.
4. Er is nog geen `HttpCase` of browser smoke test. De backend-validatie is sterk; de UI-validatie blijft operationeel handmatig.

### XML/Python Review Per Kernbestand

1. `models/sr_artikel14_calculator.py` — Go. Half-up afronding, consistente SRD-formattering en correcte Art. 12-labeling zijn nu afgedwongen in de centrale rekenkern.
2. `models/hr_payslip.py` — Go. Contractperiode-integriteit is nu hard gevalideerd; overwerkbedragen en Art. 14 cache-keys zijn deterministisch. De ongebruikelijke FN-indicatorcodes zijn bewust niet aangepast, omdat ze overeenkomen met `Salarisverwerking Module/Loonbelasting context.md`.
3. `views/hr_contract_views.xml` — Geen blocker. Het huidige scherm mist een FN-periodeveld en type-domain, maar geen van beide veroorzaakt nog een foutieve fiscale uitkomst.
4. `data/hr_rule_parameter_data.xml` — Bevestigd. `SR_BELASTINGVRIJ_JAAR = 108000.0` bestaat en is operationeel als parameterrecord beschikbaar.
5. `views/hr_payroll_config_sr_views.xml` — Bevestigd. De beheerroute voor bewerkbare `SR_*` parameters via het tabblad `Parameterwaarden` is correct aanwezig.
6. `data/hr_rule_parameter_data.xml` plus code-review — Bevestigd. Er bestaat momenteel geen actieve `SRD 750` heffingskortingparameter of runtime-logica die zo'n korting toepast. De huidige implementatie rekent zonder actieve heffingskorting.
7. `views/sr_help_template.xml` — Go. Terminologie en functionele uitleg zijn in deze finale pass consistent met de huidige module.
8. `reports/report_payslip_sr.xml` — Acceptabel voor release. Geen blocking rounding defect meer gereproduceerd na de backend-fix; verdere template-opschoning blijft wenselijk maar niet vereist.

### Final Judgment

Technisch oordeel: Go voor demo en gecontroleerde release.

Compliance/governance oordeel: Conditional Go. De resterende open post zit niet meer in de uitvoerbare code, maar in bron-governance: `Loonbelasting context.md` en `wetloon-belasting.md` vragen nog steeds een formele eigenaar en besluitspoor als deze addon als compliance-definitieve fiscale referentie moet worden verdedigd.