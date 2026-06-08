# Technische deep-dive: Odoo en l10n_sr_hr_payroll

Dit document gaat dieper dan de algemene handleiding. Het doel is dat je de
technische kant van Odoo en jouw payrollmodule echt begrijpt: hoe Odoo laadt,
hoe Python-modellen werken, hoe XML-records gekoppeld worden, hoe de payroll
engine rekent, hoe security werkt, en hoe je fouten systematisch debugt.

De module waar dit document over gaat:

```text
l10n_sr_hr_payroll
```

Deze module draait bovenop:

```python
depends = ['hr_payroll']
```

Dat betekent dat de module gebruikmaakt van bestaande Odoo Payroll modellen en
die uitbreidt.

## 1. De technische lagen van Odoo

Odoo bestaat technisch uit deze lagen:

```text
Browser
  -> Odoo webclient
    -> HTTP/RPC request
      -> Python controller/model method
        -> ORM
          -> PostgreSQL
```

De browser toont de interface. De Odoo webclient stuurt requests naar de server.
De server voert Python-code uit. Python gebruikt de ORM om database-records te
lezen en schrijven. PostgreSQL bewaart alle data.

In jouw module zie je al deze lagen:

- Browser/UI: views in `views/` en `wizard/`.
- HTTP route: `controllers/main.py`.
- Python models: `models/`.
- ORM records: `self.env['hr.payslip']`, `self.env['hr.contract']`.
- SQL-view: `models/hr_payroll_tax_report.py`.
- PostgreSQL indexes: `models/hr_payroll_indexes.py`.

## 2. Hoe Odoo een module laadt

Wanneer je een module installeert of updatet, doet Odoo ongeveer dit:

1. Lees `__manifest__.py`.
2. Controleer `depends`.
3. Importeer Python via `__init__.py`.
4. Registreer modellen en velden in de registry.
5. Maak of wijzig databasekolommen voor gewone modellen.
6. Laad XML/CSV-bestanden uit de manifestvolgorde.
7. Maak views, menus, actions, rapporten en datarecords.
8. Draai `init()` methodes voor modellen die dat nodig hebben.
9. Update module status in `ir_module_module`.

Belangrijk: Python wordt geregistreerd voordat XML wordt geladen. Daarom kan XML
verwijzen naar modellen en velden die in Python zijn gedefinieerd.

Als je een Python-bestand toevoegt maar niet importeert in `models/__init__.py`,
dan bestaat het model of veld technisch niet voor Odoo.

## 3. De Odoo registry

De registry is Odoo's interne geheugen van alle modellen, velden, methods,
views en metadata voor een database.

Als Odoo start of een module update, bouwt Odoo de registry op. Daarom moet je na
Python-wijzigingen meestal:

- Odoo herstarten, of
- module updaten via de Odoo CLI.

XML-wijzigingen vragen meestal een module update. Python-wijzigingen vragen
meestal ook een server restart, zeker op Windows service-installaties.

## 4. Het verschil tussen gewone modellen en transient models

Gewone modellen:

```python
class HrContractSrLine(models.Model):
    _name = 'hr.contract.sr.line'
```

Deze records blijven bestaan in de database.

Transient models:

```python
class SrPayrollBankExportWizard(models.TransientModel):
    _name = 'sr.payroll.bank.export.wizard'
```

Deze records zijn tijdelijk. Odoo ruimt ze later automatisch op. Ze zijn bedoeld
voor wizards, popups, exports en tijdelijke gebruikersinvoer.

In jouw module zijn de bestanden onder `wizard/` bijna allemaal
`models.TransientModel`.

## 5. `_name`, `_inherit` en `_auto`

### Nieuw model

```python
class SrPublicHoliday(models.Model):
    _name = 'sr.public.holiday'
```

Dit maakt een nieuw Odoo-model. Odoo maakt normaal ook een database tabel.

### Bestaand model uitbreiden

```python
class HrContract(models.Model):
    _inherit = 'hr.contract'
```

Dit voegt velden en methods toe aan een bestaand model.

### SQL-view model

```python
class HrPayrollTaxReport(models.Model):
    _name = 'hr.payroll.tax.report'
    _auto = False
```

`_auto = False` betekent: Odoo maakt geen gewone tabel. De developer moet zelf
een database object maken, meestal een SQL-view in `init()`.

Jouw `hr.payroll.tax.report` gebruikt dit voor een live fiscaal overzicht.

## 6. Odoo ORM: recordsets

In Odoo werk je niet met losse objecten, maar met recordsets.

Voorbeeld:

```python
payslips = self.env['hr.payslip'].search([
    ('state', 'in', ['done', 'paid']),
])
```

`payslips` kan nul, een of meerdere records bevatten.

Belangrijke regels:

- `self` is vaak een recordset.
- Gebruik `self.ensure_one()` als je precies een record verwacht.
- Methods kunnen op meerdere records tegelijk worden aangeroepen.
- Loops zoals `for slip in self:` zijn normaal.

Voorbeeld:

```python
def action_print_sr_payslip(self):
    self.ensure_one()
    ...
```

Dit voorkomt dat een methode per ongeluk op meerdere loonstroken tegelijk werkt.

## 7. `self.env`

`self.env` is je toegang tot Odoo.

Je gebruikt het voor:

```python
self.env['hr.contract']
self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
self.env.company
self.env.user
self.env.context
```

Belangrijke onderdelen:

- `self.env['model.name']`: toegang tot een model.
- `self.env.ref('module.xml_id')`: record ophalen via XML ID.
- `self.env.company`: actieve company.
- `self.env.user`: actieve gebruiker.
- `self.env.context`: extra runtime-informatie.
- `self.env.cr`: database cursor voor SQL.

## 8. Context

Context is een dictionary die Odoo meeneemt bij calls.

Voorbeeld:

```python
self.env(context=dict(self.env.context, allowed_company_ids=[company.id]))
```

Context wordt gebruikt voor:

- actieve company;
- taal;
- timezone;
- default waarden;
- flags die gedrag sturen;
- testcontext.

Context is krachtig, maar kan ook verwarrend zijn. Als iets anders werkt per
gebruiker of per company, controleer altijd context en company.

## 9. `sudo()`

`sudo()` voert een actie uit met hogere rechten.

Voorbeeld:

```python
self.env['ir.config_parameter'].sudo().get_param(key)
```

Dit is normaal voor systeemparameters, omdat gewone gebruikers die niet altijd
mogen lezen.

Gebruik `sudo()` voorzichtig. Als je te snel `sudo()` gebruikt, omzeil je security
en multi-company regels. Voor payroll kan dat gevaarlijk zijn.

Goede vraag bij elke `sudo()`:

```text
Moet deze methode echt rechten omzeilen, of maskeer ik een access-probleem?
```

## 10. Field types technisch

Veelgebruikte velden:

```python
fields.Char()
fields.Float()
fields.Monetary(currency_field='currency_id')
fields.Integer()
fields.Boolean()
fields.Selection([...])
fields.Date()
fields.Datetime()
fields.Many2one('res.company')
fields.One2many('hr.contract.sr.line', 'contract_id')
fields.Many2many('hr.contract.sr.line.type')
fields.Html()
fields.Binary()
```

Relationele velden:

- `Many2one`: veel records linken naar een record.
- `One2many`: inverse van `Many2one`.
- `Many2many`: meerdere records aan beide kanten.

Voorbeeld:

```python
sr_vaste_regels = fields.One2many(
    'hr.contract.sr.line',
    'contract_id',
)
```

Dit betekent: een contract heeft meerdere SR contractregels. Op
`hr.contract.sr.line` staat dan een `contract_id`.

## 11. Computed fields

Een computed field wordt berekend door een methode.

Voorbeeldconcept:

```python
sr_preview_netto = fields.Monetary(compute='_compute_sr_preview')
```

De methode:

```python
@api.depends('wage', 'sr_salary_type')
def _compute_sr_preview(self):
    for contract in self:
        contract.sr_preview_netto = ...
```

Technische aandachtspunten:

- Iedere record in `self` moet een waarde krijgen.
- Dependencies moeten compleet zijn.
- `store=True` betekent: waarde wordt opgeslagen in database.
- Zonder `store=True` wordt de waarde live berekend.

Bij payroll is `store=True` handig voor snapshots en rapportages, maar gevaarlijk
als dependencies fout zijn.

## 12. Onchange

`@api.onchange` draait in de UI wanneer een gebruiker een veld verandert.

Voorbeeld:

```python
@api.onchange('wage')
def _onchange_wage(self):
    ...
```

Belangrijk:

- Onchange draait niet altijd bij imports, scripts of backend create/write.
- Onchange is dus geen echte validatie.
- Gebruik constraints voor harde regels.

Voorbeeld: een negatief loon in de UI terugzetten is handig, maar de echte
bescherming moet met `@api.constrains` of `write/create` gebeuren.

## 13. Constraints

Constraints valideren records bij opslaan.

Voorbeeld:

```python
@api.constrains('wage')
def _check_non_negative_wage(self):
    for contract in self:
        if contract.wage < 0:
            raise ValidationError(...)
```

In jouw module worden constraints gebruikt voor:

- negatieve lonen;
- aantal kinderen;
- wisselkoersen;
- schijfgrenzen;
- percentages;
- overwerk multipliers;
- payroll settings.

Constraints zijn essentieel voor payrollkwaliteit.

## 14. Overrides: `create`, `write`, `unlink`

Odoo laat je standaardmethodes overschrijven.

Voorbeeld:

```python
def write(self, vals):
    ...
    return super().write(vals)
```

Gebruik dit voor:

- extra validatie;
- snapshots;
- blokkeren van wijzigingen;
- synchronisatie;
- auditgedrag.

In jouw module:

- `hr.contract.write()` bewaakt salary type wijzigingen bij bestaande loonstroken.
- `hr.payslip.compute_sheet()` voegt snapshot- en payrolllogica toe.
- `hr.payroll.tax.report.create/write/unlink()` blokkeren wijzigingen omdat het
  een read-only SQL-view is.

Belangrijk: roep meestal `super()` aan, tenzij je bewust alles blokkeert.

## 15. XML datarecords

XML records worden geladen door Odoo:

```xml
<record id="sr_rule_loonbelasting" model="hr.salary.rule">
    <field name="name">Loonbelasting (Artikel 14 WLB)</field>
    <field name="code">SR_LB</field>
</record>
```

Technisch maakt Odoo:

- een record in `hr.salary.rule`;
- een external ID in `ir.model.data`;
- koppeling tussen `l10n_sr_hr_payroll.sr_rule_loonbelasting` en record ID.

Als je hetzelfde XML ID opnieuw laadt, update Odoo het bestaande record.

## 16. `noupdate`

In XML zie je:

```xml
<data noupdate="0">
```

Of soms:

```xml
<data noupdate="1">
```

Betekenis:

- `noupdate="0"`: Odoo mag record updaten bij module update.
- `noupdate="1"`: Odoo maakt record bij installatie, maar update het later niet
  automatisch.

Voor payrollparameters is dit belangrijk. Soms wil je wettelijke defaults
updaten, maar soms wil je gebruikersinstellingen niet overschrijven.

## 17. XML view inheritance

Odoo views kunnen andere views uitbreiden met XPath.

Concept:

```xml
<field name="inherit_id" ref="hr_contract.hr_contract_view_form"/>
<field name="arch" type="xml">
    <xpath expr="//field[@name='wage']" position="after">
        <field name="sr_salary_type"/>
    </xpath>
</field>
```

Als de XPath niet matcht, krijg je een view error bij module update.

Veel technische Odoo-fouten zitten in:

- verkeerde XPath;
- veld bestaat niet;
- view wordt geladen voordat model/veld bestaat;
- verkeerd `inherit_id`;
- fout in XML syntax.

## 18. Actions en menus

Een menu opent meestal een action.

Action:

```xml
<record id="action_sr_payroll_tax_report" model="ir.actions.act_window">
    <field name="res_model">hr.payroll.tax.report</field>
    <field name="view_mode">list,pivot,form</field>
</record>
```

Menu:

```xml
<menuitem id="menu_sr_tax_report"
          action="action_sr_payroll_tax_report"/>
```

Technisch:

- menu bepaalt navigatie;
- action bepaalt welk model en welke views openen;
- views bepalen schermlayout;
- security bepaalt of gebruiker het mag zien.

## 19. Payroll engine technisch

Odoo Payroll berekent een loonstrook via salarisregels.

De payroll engine gebruikt:

- contract;
- werknemer;
- worked days;
- inputs;
- salary structure;
- salary rules;
- categories;
- rule parameters.

Elke salary rule heeft:

- `code`;
- `sequence`;
- `category_id`;
- condition;
- amount computation;
- zichtbaarheid.

De sequence bepaalt de volgorde. Dat is technisch heel belangrijk, omdat latere
regels eerdere resultaten kunnen gebruiken.

Voorbeeld:

```python
result = categories['BASIC'] + categories['ALW'] + categories['SR_GRD']
```

Deze regel werkt alleen als `BASIC`, `ALW` en `SR_GRD` eerder zijn gevuld.

## 20. Salary rule localdict

In salary rule Python-code heb je variabelen zoals:

- `payslip`
- `contract`
- `employee`
- `categories`
- `rules`
- `worked_days`
- `inputs`
- `result`

Voorbeeld uit jouw module:

```python
result = -float_round(
    payslip._sr_artikel14_lb(categories['GROSS'], aftrek_bv=aftrek_bv),
    precision_digits=2,
)
```

Technisch betekent dit:

1. Salary rule roept een methode op de loonstrook aan.
2. Die methode haalt parameters op.
3. Die methode gebruikt de centrale calculator.
4. Resultaat wordt negatief gemaakt omdat LB een inhouding is.

## 21. Waarom salary rule codes heilig zijn

Codes zoals `SR_LB`, `SR_AOV`, `SR_KB_VRIJ` en `NET` worden op meerdere plekken
gebruikt:

- salary rules;
- rapportage SQL;
- QWeb rapporten;
- tests;
- exports;
- helpermethodes.

Als je een code wijzigt, moet je overal zoeken:

```powershell
rg "SR_LB"
```

Anders kan de loonstrook nog rekenen, maar het rapport mist bedragen.

## 22. Artikel 14 calculator technisch

`models/sr_artikel14_calculator.py` is bewust functioneel opgezet. Het bevat
losse functies, niet een Odoo modelclass.

Belangrijke functies:

- `get_sr_parameter_value(...)`
- `fetch_params_from_rule_parameter(...)`
- `calculate_lb(...)`
- `generate_breakdown_html(...)`
- `generate_tax_bracket_html(...)`

Waarom dit technisch goed is:

- minder afhankelijk van Odoo state;
- makkelijker testbaar;
- dezelfde code kan op contract en payslip gebruikt worden;
- minder duplicatie.

De calculator gebruikt `Decimal` voor geldafronding. Dat is beter dan gewone
floating point wanneer fiscale afronding belangrijk is.

## 23. Parameterresolutie technisch

De module zoekt parameterwaarden ongeveer zo:

```text
ir.config_parameter override
  -> hr.rule.parameter op ref_date
    -> hardcoded fallback
      -> UserError
```

Dit zit in `get_sr_parameter_value`.

Waarom dit belangrijk is:

- settings kunnen live waarden overrulen;
- historische parameters blijven mogelijk;
- payroll kan per loonstrookdatum juiste waarden gebruiken;
- ontbrekende configuratie geeft een duidelijke fout.

## 24. Loonstrook snapshots technisch

In `hr.payslip` staan velden zoals:

- `sr_frozen_contract_currency_id`
- `sr_frozen_exchange_rate`
- `sr_exchange_rate`
- `sr_netto_bronvaluta`
- `sr_bruto_bronvaluta`
- `sr_belastingvrij_periode_srd`

Deze waarden worden rond `compute_sheet()` opgeslagen.

Technisch doel:

- confirmed loonstroken reproduceerbaar maken;
- rapportages laten lezen uit stabiele data;
- wisselkoerswijzigingen later niet laten doorwerken;
- audit trail verbeteren.

## 25. SQL-view technisch

`hr.payroll.tax.report` gebruikt `_auto = False` en maakt een SQL-view.

Een SQL-view is een virtuele tabel:

```sql
CREATE OR REPLACE VIEW hr_payroll_tax_report AS (...)
```

Odoo ziet de view alsof het een model is, zolang:

- de view een unieke `id` kolom heeft;
- velden overeenkomen met Python field names;
- datatypes kloppen.

Jouw view telt payroll lines op met `SUM(CASE WHEN hpl.code IN (...) THEN ...)`.

Voordeel:

- snel;
- live;
- geschikt voor list en pivot;
- geen aparte sync nodig.

Nadeel:

- niet direct wijzigbaar;
- elke nieuwe salary rule code moet bewust in de query;
- SQL-fouten breken module update of rapportweergave.

## 26. Database indexes technisch

Indexes versnellen zoekopdrachten.

Zonder index kan PostgreSQL veel rijen moeten scannen. Bij payroll kan dat traag
worden, omdat elke loonstrook meerdere regels, inputs en work entries heeft.

`hr_payroll_indexes.py` voegt indexes toe op velden die vaak worden gebruikt voor:

- joins;
- filters;
- rapportages;
- payroll searches.

Indexes zijn vooral nuttig voor rapportages en batchberekeningen.

## 27. Security technisch

Odoo security werkt in lagen:

```text
Groups
  -> ir.model.access.csv
    -> record rules
      -> field/view visibility
```

### Groups

Groepen bepalen rollen, zoals payroll user, payroll manager of accountant export.

### Access CSV

CSV bepaalt per model:

```text
read, write, create, unlink
```

Als access ontbreekt, krijg je vaak:

```text
Access Error
```

### Record rules

Record rules filteren welke records zichtbaar zijn. In jouw module is er een
multi-company rule voor het fiscale overzicht:

```python
['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
```

Dat betekent: gebruiker ziet alleen records zonder company of binnen toegestane
companies.

## 28. Multi-company technisch

Odoo kan meerdere bedrijven in een database hebben. Dat raakt payroll sterk.

Technische aandachtspunten:

- `company_id` op records;
- `check_company=True` op Many2one velden;
- `allowed_company_ids` in context;
- record rules met `company_ids`;
- `self.env.company`.

Als data "verdwijnt", is het vaak geen bug in de berekening maar een
multi-company/security filter.

## 29. Wizards technisch

Een wizard heeft meestal:

1. fields voor user input;
2. view XML voor popup;
3. button die `action_*` methode aanroept;
4. methode die rapport/export maakt;
5. return action.

Voor CSV-downloads zie je vaak:

```python
return {
    'type': 'ir.actions.act_url',
    'url': '/web/content?...',
    'target': 'self',
}
```

Technisch maakt de wizard een binary veld met file content en laat Odoo dat
downloaden via `/web/content`.

## 30. QWeb rapporten technisch

QWeb rapporten zijn XML templates.

Ze krijgen data van:

- het record zelf;
- een report action;
- helpermethodes;
- wizarddata.

Veelvoorkomende QWeb onderdelen:

```xml
<t t-if="condition">
<t t-foreach="records" t-as="record">
<span t-field="record.name"/>
<span t-esc="value"/>
```

Gebruik:

- `t-field` voor Odoo velden met formatting;
- `t-esc` voor berekende waarden;
- vermijd rauwe HTML tenzij nodig.

## 31. Controller technisch

`controllers/main.py` definieert een route:

```python
@http.route('/sr_payroll/help', type='http', auth='user', csrf=False)
```

Technisch:

- `type='http'`: gewone HTTP response.
- `auth='user'`: gebruiker moet ingelogd zijn.
- `request.env`: environment voor de request.
- `request.render(...)`: render QWeb template.

De controller gebruikt `SUPERUSER_ID` voor het ophalen van parameters, maar
controleert eerst de gebruikersgroep. Dat is belangrijk: data ophalen met hoge
rechten, maar toegang eerst beperken.

## 32. Tests technisch

Odoo tests gebruiken meestal:

```python
from odoo.tests import common, tagged

@tagged('post_install', '-at_install')
class TestSomething(common.TransactionCase):
    ...
```

`TransactionCase` geeft elke test een transactionele omgeving.

In jouw tests zie je patronen:

- testbedrijf maken;
- werknemer maken;
- contract maken;
- loonstrook maken;
- `compute_sheet()` draaien;
- salary line totals controleren.

Dit is precies hoe payroll getest moet worden: niet alleen losse calculator
testen, maar ook de volledige Odoo payrollflow.

## 33. Odoo CLI technisch

Een typische test/update command ziet er zo uit:

```powershell
..\python\python.exe .\odoo-bin `
  -c .\odoo.conf `
  -d Salarisverwerking-Module `
  -u l10n_sr_hr_payroll `
  --test-enable `
  --stop-after-init `
  --no-http
```

Betekenis:

- `-c`: configbestand.
- `-d`: database.
- `-u`: module updaten.
- `--test-enable`: tests aanzetten.
- `--stop-after-init`: stoppen na update/test.
- `--no-http`: geen webserver starten.

## 34. Debugging: eerst classificeren

Classificeer een fout altijd eerst.

### Install/update error

Waarschijnlijk:

- manifestvolgorde;
- XML syntax;
- view inheritance;
- missing external ID;
- Python import;
- model/field bestaat niet.

### Runtime UI error

Waarschijnlijk:

- access rights;
- record rule;
- field/view issue;
- onchange/compute fout;
- context/company.

### Payroll calculation error

Waarschijnlijk:

- salary rule sequence;
- category;
- parameter;
- snapshot;
- contractregelcategorie;
- FN/maandloon;
- valuta.

### Report/export error

Waarschijnlijk:

- QWeb template;
- SQL-view;
- missing salary rule code in query;
- wizard domain;
- confirmed state filter;
- access.

## 35. Debug commands

Zoeken naar code:

```powershell
rg "SR_LB"
rg "_sr_artikel14_lb"
rg "sr_exchange_rate"
rg "hr.payroll.tax.report"
```

Alle Python classes vinden:

```powershell
rg "^class " models wizard controllers
```

Alle modelnamen vinden:

```powershell
rg "_name =|_inherit =" models wizard
```

Alle salary rule codes vinden:

```powershell
rg "<field name=\"code\">" data\hr_salary_rule_data.xml
```

Alle references naar een XML ID vinden:

```powershell
rg "sr_payroll_structure"
```

Git status:

```powershell
git status --short
```

## 36. Technische checklist bij een fout

Gebruik deze lijst:

1. Wat is de exacte foutmelding?
2. Gebeurt het bij install, update, UI, save, compute, print of export?
3. Welk model is betrokken?
4. Bestaat het veld technisch in Python?
5. Is het Python-bestand geimporteerd?
6. Staat het XML-bestand in `__manifest__.py`?
7. Bestaat de XML ID?
8. Wordt het bestand in de juiste volgorde geladen?
9. Heeft de gebruiker access rights?
10. Filtert een record rule het record weg?
11. Is de juiste company actief?
12. Is de loonstrook draft, done of paid?
13. Zijn snapshots gevuld?
14. Kloppen salary rule sequence en category?
15. Klopt de parameter voor de loonstrookdatum?

## 37. Technische checklist bij een wijziging

Voor elke wijziging:

1. Zoek alle bestaande references met `rg`.
2. Bepaal of het model, view, data, report of security raakt.
3. Bepaal of de wijziging oude loonstroken mag raken.
4. Bepaal of het een parameter moet zijn.
5. Bepaal of multi-currency geraakt wordt.
6. Bepaal of FN-loon geraakt wordt.
7. Bepaal of SQL-view en exports mee moeten.
8. Voeg of update tests.
9. Update module.
10. Controleer logs.

## 38. Wat je uit je hoofd moet kennen

Voor deze module moet je technisch vooral dit kennen:

- `__manifest__.py` bepaalt laadvolgorde.
- `__init__.py` bepaalt welke Python-code geladen wordt.
- `_inherit` breidt bestaande Odoo modellen uit.
- `_name` maakt nieuwe modellen.
- `_auto = False` betekent SQL-view of handmatige database objecten.
- Salary rule `sequence` bepaalt berekeningsvolgorde.
- Salary rule `code` wordt overal hergebruikt.
- `categories` in payroll bevat optellingen per salary category.
- `contract` is de bron van vaste afspraken.
- `payslip` is de bron van berekende en bevroren payrollresultaten.
- `hr.rule.parameter` is datumgevoelige payrollconfiguratie.
- `ir.config_parameter` is live systeemconfiguratie.
- `sudo()` omzeilt rechten en moet bewust gebruikt worden.
- Access CSV geeft modelrechten.
- Record rules filteren records.
- Multi-company context bepaalt zichtbaarheid.
- Tests moeten echte loonstroken berekenen.

## 39. Mini-flow: van contractveld naar rapport

Voorbeeld: een vaste belastbare toelage.

```text
Contractregel
  -> hr.contract.sr.line
    -> categorie = belastbaar
      -> salary rule SR_ALW
        -> telt mee in ALW
          -> GROSS = BASIC + ALW + SR_GRD
            -> SR_LB gebruikt GROSS
              -> loonstrookregels opgeslagen
                -> SQL-view telt codes op
                  -> fiscaal overzicht toont bedrag
```

Als het rapport fout is, kan de fout op elke stap zitten.

## 40. Mini-flow: van parameter naar loonstrook

Voorbeeld: tariefschijf.

```text
hr.rule.parameter / ir.config_parameter
  -> get_sr_parameter_value()
    -> fetch_params_from_rule_parameter()
      -> calculate_lb()
        -> payslip._sr_artikel14_lb()
          -> salary rule SR_LB
            -> hr.payslip.line
```

Als LB fout is, controleer parameterwaarde, referentiedatum, calculator en salary
rule.

## 41. Mini-flow: van work entry naar overwerk

```text
hr.work.entry
  -> SR velden voor geplande/extra uren
    -> classificatie 150% / 200%
      -> payslip input
        -> overwerk salary rules
          -> LB/AOV overwerk
            -> rapportage
```

Als overwerk fout is, controleer work entry dates, duration, feestdagen,
validated state, input generatie en salary rule codes.

## 42. Hoe je technisch leert zonder te verdwalen

Lees code niet willekeurig. Volg flows.

Voor contract naar loonstrook:

1. `models/hr_contract.py`
2. `data/hr_salary_rule_data.xml`
3. `models/hr_payslip.py`
4. `tests/test_article_14.py`

Voor settings naar berekening:

1. `models/res_config_settings.py`
2. `data/hr_rule_parameter_data.xml`
3. `models/sr_artikel14_calculator.py`
4. `tests/test_audit_fixes.py`

Voor rapportage:

1. `models/hr_payroll_tax_report.py`
2. `views/hr_payroll_tax_report_views.xml`
3. `wizard/sr_payroll_tax_report_export_wizard.py`
4. `reports/`

Voor security:

1. `security/ir.model.access.csv`
2. `security/l10n_sr_hr_payroll_security.xml`
3. views/actions waar menu's staan

## 43. Belangrijkste technische gedachte

Odoo is metadata-gedreven. Dat betekent:

```text
Python definieert modellen en gedrag.
XML definieert records, schermen en rapporten.
Security definieert toegang.
PostgreSQL bewaart alles.
De ORM verbindt het geheel.
```

Bijna elke fout ontstaat doordat een van die lagen niet klopt met de andere.

Als je technisch sterk wilt worden in deze module, train jezelf om steeds te
vragen:

```text
In welke laag zit ik nu?
Welke andere lagen verwijzen hiernaar?
Wat gebeurt er bij installatie, berekening en rapportage?
```

Dat is de manier waarop je Odoo-issues sneller gaat vinden en oplossen.
