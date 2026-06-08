# Odoo vanaf nul: handleiding voor l10n_sr_hr_payroll

Deze handleiding is geschreven voor iemand die deze module vanaf nul wil
begrijpen: wat Odoo is, waarom de module deze structuur heeft, welke talen en
bestanden gebruikt worden, hoe de payroll-berekening loopt, en hoe je wijzigingen
maakt zonder onnodige issues te veroorzaken.

De module in deze map heet `l10n_sr_hr_payroll`. De naam betekent:

- `l10n`: localization, dus lokale wetgeving of lokale bedrijfsregels.
- `sr`: Suriname.
- `hr_payroll`: uitbreiding op Odoo Payroll.

Kort gezegd: deze module maakt Odoo Payroll geschikt voor Surinaamse
loonverwerking volgens de Wet Loonbelasting, met onder andere Artikel 14,
Artikel 17, Artikel 17a, Artikel 17c, AOV, kinderbijslag, vaste contractregels,
multi-currency en fiscale rapportages.

## 1. Wat Odoo is

Odoo is een ERP-systeem. ERP betekent dat meerdere bedrijfsprocessen in een
systeem samenkomen: HR, payroll, verkoop, boekhouding, voorraad, projecten,
CRM, enzovoort.

Odoo bestaat uit modules. Een module is een pakket met code, schermen, data,
rechten en rapporten. Je installeert een module in een database. Daarna maakt
Odoo tabellen, velden, menu's, acties en rapporten aan op basis van de bestanden
in die module.

Belangrijk: Odoo is niet alleen Python-code. Het is een combinatie van:

- Python voor modellen, business logic, berekeningen en serveracties.
- XML voor views, menu's, rapportdefinities, datarecords en security.
- CSV voor toegangsrechten.
- JavaScript voor extra gedrag in de webclient.
- CSS/SCSS voor styling.
- QWeb/XML voor PDF-rapporten en HTML templates.
- PostgreSQL voor de database.

## 2. Hoe Odoo technisch werkt

Odoo draait als een Python-server. De gebruiker werkt in de browser. De browser
praat met de Odoo-server. De server leest en schrijft in PostgreSQL.

Een simpele flow:

1. Gebruiker opent een scherm, bijvoorbeeld een contract.
2. Odoo zoekt de juiste view in XML.
3. De view toont velden van een model, bijvoorbeeld `hr.contract`.
4. Het model is Python-code met velden en methodes.
5. Als de gebruiker opslaat, schrijft Odoo via de ORM naar PostgreSQL.
6. Als een knop wordt geklikt, voert Odoo een Python-methode uit.
7. Als een loonstrook wordt berekend, voert Odoo salarisregels en Python-methodes uit.

ORM betekent Object Relational Mapping. Je werkt in Python met records zoals:

```python
contract = self.env['hr.contract'].browse(contract_id)
contract.wage = 12000.0
```

Odoo vertaalt dat naar database-acties. Je hoeft meestal geen SQL te schrijven.
SQL wordt alleen gebruikt wanneer dat bewust nodig is, bijvoorbeeld bij een
snelle read-only rapportageview.

## 3. Het belangrijkste Odoo-denken

In Odoo moet je altijd denken in modellen, records en views.

Een model is een soort tabel plus gedrag. Voorbeelden:

- `hr.employee`: werknemer.
- `hr.contract`: contract.
- `hr.payslip`: loonstrook.
- `hr.salary.rule`: salarisregel.
- `hr.rule.parameter`: payrollparameter.

Een record is een rij in zo'n model. Een werknemer is dus een record van
`hr.employee`.

Een view bepaalt hoe records zichtbaar zijn in de interface. Views staan meestal
in XML-bestanden onder `views/` of `wizard/`.

Een action opent een scherm of start een rapport. Een menuitem hangt aan een
action.

Een security rule bepaalt wie records mag zien. Een access CSV bepaalt wie mag
lezen, maken, wijzigen of verwijderen.

## 4. Waarom deze module deze structuur heeft

De mapstructuur volgt de standaard Odoo-conventie. Dat is belangrijk, omdat Odoo
modules automatisch ontdekt en laadt op basis van vaste bestandsnamen en
patronen.

De module heeft deze hoofdstructuur:

```text
l10n_sr_hr_payroll/
  __manifest__.py
  __init__.py
  controllers/
  data/
  models/
  reports/
  security/
  static/
  tests/
  views/
  wizard/
  scripts/
```

Elke map heeft een eigen taak.

## 5. `__manifest__.py`: het startpunt van de module

Het manifest is de identiteitskaart van de module. Odoo leest dit bestand om te
weten:

- hoe de module heet;
- welke versie het is;
- van welke andere modules hij afhankelijk is;
- welke XML/CSV-bestanden geladen moeten worden;
- welke assets in de backend geladen worden;
- of de module installeerbaar is.

In deze module staat:

```python
'depends': ['hr_payroll']
```

Dat betekent: deze module kan pas werken als Odoo Payroll al aanwezig is. Dat is
logisch, want deze module vervangt Odoo Payroll niet. Hij breidt Payroll uit met
Surinaamse regels.

De volgorde in `data` is belangrijk. Odoo laadt bestanden in precies die volgorde.
Daarom staat security vroeg, daarna basisdata, daarna views, wizards en rapporten.

Bijvoorbeeld:

- Eerst groepen en toegangsrechten.
- Dan payrollstructuren.
- Dan parameters.
- Dan salarisregels.
- Dan contracttypes en inputtypes.
- Daarna views en rapporten die naar die records verwijzen.

Als je een XML-record gebruikt voordat het bestaat, krijg je een installatiefout
zoals "External ID not found".

## 6. `__init__.py`: Python-code laden

Het hoofd-bestand `__init__.py` bevat:

```python
from . import controllers
from . import models
from . import wizard
```

Dit vertelt Odoo welke Python-packages geladen moeten worden.

Daarna heeft `models/__init__.py` weer imports zoals:

```python
from . import hr_contract
from . import hr_payslip
from . import hr_payroll_tax_report
```

Zonder deze imports bestaan je Python-uitbreidingen niet in Odoo. Een veelgemaakte
fout is een nieuw modelbestand maken maar vergeten om het in `models/__init__.py`
te importeren.

## 7. De gebruikte talen

Deze module gebruikt meerdere talen en bestandsformaten.

### Python

Python wordt gebruikt voor:

- nieuwe modellen;
- uitbreidingen op bestaande Odoo-modellen;
- berekeningen;
- validations;
- onchange-logica;
- knopacties;
- wizards;
- exports;
- SQL-view initialisatie.

Voorbeeld:

```python
class HrContract(models.Model):
    _inherit = 'hr.contract'
```

Dit betekent: breid het bestaande Odoo-model `hr.contract` uit.

### XML

XML wordt gebruikt voor:

- views;
- menu's;
- actions;
- standaarddata;
- salarisregels;
- rapportdefinities;
- QWeb-rapportlayouts.

Voorbeeld:

```xml
<record id="sr_payroll_structure" model="hr.payroll.structure">
    <field name="name">Suriname - Normaal Loon</field>
</record>
```

Dit maakt of wijzigt een record in Odoo.

### CSV

CSV wordt hier gebruikt voor `security/ir.model.access.csv`. Daarin staat wie
welke rechten heeft op welke modellen.

### JavaScript

JavaScript staat onder `static/src/js/`. In deze module wordt het gebruikt voor
extra frontend-gedrag, bijvoorbeeld shortcut-lijsten.

### CSS

CSS staat onder `static/src/css/`. In deze module wordt het geladen via
`web.assets_backend` in het manifest.

### SQL

Normaal werkt Odoo via de ORM, maar deze module gebruikt SQL bewust voor het
fiscale overzicht. Het model `hr.payroll.tax.report` heeft `_auto = False`.
Dat betekent: Odoo maakt niet automatisch een tabel aan. De module maakt zelf
een PostgreSQL view.

## 8. Belangrijk verschil: `_name` en `_inherit`

In Odoo zie je vaak:

```python
_name = 'mijn.model'
```

Dat maakt een nieuw model.

Je ziet ook:

```python
_inherit = 'hr.contract'
```

Dat breidt een bestaand model uit.

In deze module gebeuren beide dingen.

Nieuwe modellen:

- `hr.contract.sr.line.type`
- `hr.contract.sr.line`
- `hr.payroll.tax.report`
- `sr.public.holiday`
- verschillende wizard-modellen

Uitbreidingen op bestaande modellen:

- `hr.contract`
- `hr.employee`
- `hr.payslip`
- `hr.payslip.run`
- `hr.salary.rule`
- `hr.rule.parameter`
- `hr.work.entry`
- `hr.work.entry.type`
- `res.company`
- `res.config.settings`

## 9. De modellenmap

De map `models/` bevat de serverlogica. Dit is de belangrijkste map om te
begrijpen.

### `models/hr_contract.py`

Dit bestand breidt contracten uit met Surinaamse payrollvelden.

Belangrijke dingen in dit bestand:

- `sr_salary_type`: maandloon of FN-loon.
- `sr_aantal_kinderen`: nodig voor kinderbijslag.
- `sr_contract_currency`: contractvaluta.
- `sr_vaste_regels`: vaste toelagen en inhoudingen.
- previewvelden voor bruto, belastbaar loon, LB, AOV en netto.
- helpers om bedragen naar SRD om te rekenen.
- validations om negatieve lonen en ongeldige waarden te voorkomen.

Waarom dit logisch is: het contract is de bron van vaste salarisafspraken. Alles
wat structureel bij een werknemer hoort, hoort meestal op het contract.

Voorbeelden:

- basisloon;
- maandloon of FN-loon;
- vaste toelage;
- pensioeninhouding;
- aantal kinderen;
- contractvaluta.

### `models/hr_contract_sr_line_type.py`

Dit model definieert soorten vaste loonregels, bijvoorbeeld:

- belastbare toelage;
- vrijgestelde vergoeding;
- inhouding;
- aftrek belastingvrij;
- fiscale grondslag.

Het type bepaalt hoe een contractregel fiscaal behandeld wordt.

### `models/hr_contract_sr_line.py`

Dit model bevat de echte vaste regels op het contract. Een regel heeft een type,
een categorie en een bedrag. De salarisregels lezen deze contractregels tijdens
de loonstrookberekening.

### `models/sr_artikel14_calculator.py`

Dit is de centrale rekenmotor voor Artikel 14. Dit bestand is bewust losser
gemaakt van de Odoo-modellen. Het bevat functies die parameters aannemen en een
berekening teruggeven.

Waarom dat slim is:

- dezelfde berekening kan gebruikt worden door contractpreview en loonstrook;
- tests kunnen de berekening direct controleren;
- minder dubbele logica;
- minder kans dat preview en echte loonstrook uit elkaar lopen.

Belangrijke onderdelen:

- ophalen en normaliseren van parameters;
- dynamische belasting schijven;
- afronding met `Decimal` en `ROUND_HALF_UP`;
- berekening van forfaitaire aftrek;
- berekening van belastbaar jaarloon;
- berekening van LB per jaar en per periode;
- berekening van AOV;
- HTML breakdown voor uitleg in de UI.

### `models/hr_payslip.py`

Dit is het hart van de loonstrooklogica.

Belangrijke taken:

- herkennen of een loonstrook een SR-loonstrook is;
- bevriezen van contractvaluta en wisselkoers;
- opslaan van summary snapshots;
- genereren en synchroniseren van overwerk-inputs;
- valideren van FN-periodes 2026;
- berekenen van Artikel 14 LB en AOV;
- bijzondere beloningen behandelen;
- jaarlijkse FN-correcties;
- print- en previewacties.

Waarom snapshots belangrijk zijn: payroll moet later controleerbaar blijven.
Als een wisselkoers of parameter later wijzigt, mag een bevestigde loonstrook
niet stilletjes anders worden. Daarom bewaart de loonstrook bevroren waarden.

### `models/hr_payroll_tax_report.py`

Dit is het fiscale belastingoverzicht. Het model heeft:

```python
_auto = False
```

Dat betekent dat het geen gewone Odoo-tabel is, maar een SQL-view. De view leest
bevestigde en betaalde SR-loonstroken en vat regels samen, bijvoorbeeld:

- bruto loon;
- LB totaal;
- LB Artikel 14;
- LB bijzondere beloningen;
- AOV;
- kinderbijslag;
- netto SRD;
- netto bronvaluta.

Het model is read-only. `create`, `write` en `unlink` geven bewust een fout.
Correcties moeten op de loonstrook gebeuren, niet direct in het rapport.

### `models/res_config_settings.py`

Dit bestand voegt SR Payroll instellingen toe aan Odoo Settings.

Voorbeelden:

- belastingvrije voet;
- forfaitair percentage;
- schijfgrenzen;
- tarieven;
- AOV-tarief;
- AOV-franchise;
- kinderbijslaglimieten;
- overwerktarieven;
- wisselkoersen;
- standaard loonstrooklayout.

Instellingen worden vaak opgeslagen in `ir.config_parameter`. Dat is Odoo's
centrale opslag voor systeemparameters.

### `models/res_company.py`

Dit breidt bedrijven uit met company-specifieke payrollconfiguratie, zoals:

- loonstrooktemplate;
- standaard contractvaluta;
- wisselkoersen voor USD en EUR;
- shortcut instellingen.

### `models/hr_work_entry.py`

Work entries zijn werkuren of afwezigheden die payroll kan gebruiken. Deze module
breidt work entries uit voor Surinaamse overwerklogica:

- normale uren;
- extra uren;
- overwerk 150%;
- overwerk 200%;
- feestdaglogica;
- handmatige overrides;
- validatie van onredelijke duur.

### `models/hr_work_entry_type.py`

Dit voegt flags toe aan work entry types, zoals of een type overwerk is en welke
multiplier erbij hoort.

### `models/hr_salary_rule.py`

Dit bestand helpt salarisregels te synchroniseren, vooral voor uurloonstructuren.
De payrollregels zelf staan in XML onder `data/hr_salary_rule_data.xml`.

### `models/hr_rule_parameter.py`

Dit breidt Odoo's payrollparameters uit. Parameters kunnen een historie hebben
per datum. Dat is belangrijk bij payroll, omdat een loonstrook van april 2026
met de waarden van april 2026 moet rekenen.

### `models/hr_employee.py`

Dit breidt werknemers uit met extra velden die nodig zijn voor rapportages of
Surinaamse payrollcontext.

### `models/hr_payslip_input.py` en `models/hr_payslip_input_type.py`

Payslip inputs zijn losse invoerbedragen op een loonstrook. Denk aan een
eenmalige toelage, extra inhouding, bijzondere beloning of overwerkbedrag.

### `models/hr_payslip_run.py`

Een payslip run is een batch loonstroken. Dit bestand voegt Surinaamse acties of
helpers toe aan de loonrun.

### `models/sr_public_holiday.py`

Dit is een eigen model voor Surinaamse wettelijke feestdagen. Het wordt gebruikt
voor overwerk- en dagtype-logica.

### `models/hr_payroll_indexes.py`

Dit bestand maakt database-indexes aan. Indexes maken zoeken en rapportages
sneller. Dit is vooral belangrijk bij payrollregels, loonstroken en work entries.

## 10. De datamap

De map `data/` bevat records die Odoo bij installatie of update laadt.

Belangrijke bestanden:

- `hr_payroll_structure_type_data.xml`
- `hr_payroll_structure_data.xml`
- `hr_rule_parameter_data.xml`
- `ir_config_parameter_data.xml`
- `hr_salary_rule_data.xml`
- `hr_payslip_input_type_data.xml`
- `hr_contract_sr_line_type_data.xml`
- `hr_payslip_server_action_data.xml`
- `res_currency_srd_data.xml`
- `sr_public_holiday_data.xml`

### Payroll structure type

Een structure type zegt welk soort contract/payroll het is. Deze module heeft
onder andere:

- Suriname normaal loon.
- Suriname uurloon.

### Payroll structure

Een structure is de set salarisregels die voor een loonstrook wordt gebruikt.
Deze module heeft een Surinaamse structuur voor normaal loon en een structuur
voor uurloon.

### Rule parameters

`hr.rule.parameter` bevat fiscale parameters met een datumversie. Dit is goed
voor wettelijke payroll, omdat tarieven en grenzen kunnen wijzigen.

### Config parameters

`ir.config_parameter` bevat live instellingen. In deze module krijgen config
parameters prioriteit als ze expliciet zijn ingesteld. Daarna valt de code terug
op `hr.rule.parameter`, en daarna op defaults in de calculator.

### Salary rules

`data/hr_salary_rule_data.xml` bevat de loonstrookregels. De sequence is hier
heel belangrijk. Odoo berekent salarisregels in sequence-volgorde.

Globale flow:

```text
10  BASIC              basisloon
20  SR_ALW             belastbare contracttoelagen
21  SR_KB_BELAST       belastbaar deel kinderbijslag
22  SR_VGB_BELAST      fiscaal voordeel in natura
23  SR_INPUT_BELASTB   belastbare payslip inputs
30  GROSS              bruto belastbare grondslag
50  SR_LB              loonbelasting Artikel 14
55  SR_HK              heffingskorting snapshot/informatie
60  SR_AOV             AOV
65  SR_AFTREK_BV       aftrek belastingvrij
70  SR_PENSIOEN        vaste inhoudingen
73  SR_INPUT_AFTREK    extra inhoudingen
80  SR_KINDBIJ         vrijgestelde vergoedingen
81  SR_KB_VRIJ         vrijgesteld deel kinderbijslag
82  SR_INPUT_VRIJ      vrijgestelde inputs
84-89                  overwerk en bijzondere beloningen
91-92                  LB/AOV bijzondere beloningen
100 NET                netto loon
```

Als je een nieuwe salarisregel toevoegt, moet je goed nadenken over:

- sequence;
- category;
- code;
- of de regel positief of negatief is;
- of hij in `GROSS` moet vallen;
- of hij in `NET` moet vallen;
- of hij zichtbaar moet zijn op de loonstrook;
- of rapportages hem moeten meenemen.

## 11. Views

De map `views/` bevat XML-schermen voor gewone modellen.

Voorbeelden:

- `hr_contract_views.xml`: extra tabbladen/velden op contracten.
- `hr_employee_views.xml`: extra velden op werknemer.
- `hr_payslip_run_views.xml`: knoppen en overzichten op loonruns.
- `hr_work_entry_views.xml`: overwerk/work-entry schermen.
- `res_config_settings_views.xml`: instellingenpagina.
- `hr_payroll_tax_report_views.xml`: fiscaal overzicht.
- `hr_payroll_dashboard_views.xml`: dashboard/menu structuur.
- `hr_payroll_help_views.xml` en `sr_help_template.xml`: help-pagina.

Views veranderen meestal niet de business logic. Ze bepalen vooral wat de
gebruiker ziet en welke knoppen beschikbaar zijn.

## 12. Wizards

De map `wizard/` bevat transient models. Een transient model is tijdelijk. Het
wordt gebruikt voor popup-schermen, exports en acties die invoer vragen.

In deze module:

- `sr_payroll_annual_statement_wizard.py`: jaaropgave PDF.
- `sr_payroll_tax_report_export_wizard.py`: fiscaal overzicht CSV.
- `sr_payroll_company_year_wizard.py`: bedrijfsjaaroverzicht.
- `sr_payroll_verzamelloonstaat_wizard.py`: verzamelloonstaat export.
- `sr_payroll_period_wizard.py`: periode rapporten.
- `sr_payroll_bank_export_wizard.py`: bankexport betaalbestand.

Waarom wizards apart staan: ze zijn geen permanente payrollgegevens, maar een
manier om een gebruiker een actie te laten starten met parameters zoals jaar,
bedrijf, periode of loonrun.

## 13. Reports

De map `reports/` bevat QWeb/XML rapporten. Deze worden gebruikt voor PDF's en
HTML-weergave.

Voorbeelden:

- loonstrookrapport;
- fiscale overzichten;
- maandaangifte;
- jaaropgave;
- bedrijfsperiodeoverzicht;
- bedrijfsjaaroverzicht.

QWeb lijkt op XML/HTML met Odoo-instructies. Je ziet bijvoorbeeld loops,
conditions en velden die in het rapport worden geplaatst.

Bij rapporten moet je extra voorzichtig zijn met:

- lege waarden;
- bedragen afronden;
- layout op meerdere pagina's;
- juiste valuta;
- rechten;
- data die uit bevestigde loonstroken moet komen.

## 14. Security

Security bestaat hier uit:

- `security/l10n_sr_hr_payroll_security.xml`
- `security/ir.model.access.csv`

De XML maakt onder andere een extra groep:

- `SR Payroll Accountant Export`

Die groep krijgt exportrechten en toegang tot relevante rapportage.

De CSV bepaalt rechten per model. Bijvoorbeeld:

- payroll users mogen vaste contractregels lezen en maken/wijzigen maar niet verwijderen;
- payroll managers mogen meer;
- tax report is read-only;
- wizards mogen worden aangemaakt omdat ze tijdelijke records nodig hebben.

Veel Odoo-issues komen door security:

- model heeft geen access rule;
- gebruiker zit niet in juiste groep;
- record rule filtert records weg;
- multi-company domein sluit bedrijf uit.

## 15. Controllers

De map `controllers/` bevat HTTP routes.

In deze module is er een helpcontroller:

```python
@http.route('/sr_payroll/help', type='http', auth='user', csrf=False)
```

Deze route toont een help-pagina met actuele payrollparameters. De controller
controleert eerst of de gebruiker in een toegestane groep zit.

Controllers gebruik je wanneer je een eigen URL of webpagina nodig hebt buiten
de standaard Odoo views.

## 16. Static files

De map `static/` bevat frontend-bestanden:

- `static/src/css/l10n_sr_payroll.css`
- `static/src/js/sr_shortcut_list.js`
- `static/src/xml/sr_shortcut_list.xml`
- `static/description/icon.png`

Het manifest laadt de CSS via:

```python
'assets': {
    'web.assets_backend': [
        'l10n_sr_hr_payroll/static/src/css/l10n_sr_payroll.css',
    ],
},
```

Assets worden gebruikt door de Odoo backend webclient.

## 17. Tests

De map `tests/` bevat regressietests en integratietests. Deze zijn erg belangrijk
voor payroll, omdat kleine wijzigingen in fiscale logica snel grote gevolgen
hebben.

Belangrijke testbestanden:

- `test_article_14.py`
- `test_article_14_integration.py`
- `test_audit_fixes.py`
- `test_currency_integration.py`
- `test_report_exports.py`
- `test_sr_vaste_regels.py`
- `test_qa_audit_2026.py`

Deze tests controleren onder andere:

- Artikel 14 berekening;
- schijfgrenzen;
- forfaitaire aftrek;
- kinderbijslag;
- pensioenpremie;
- maandloon versus FN-loon;
- bijzondere beloningen;
- multi-currency;
- wisselkoers snapshots;
- rapportages;
- security en performance-indexes;
- overwerk work entries.

## 18. Scripts

De map `scripts/` bevat hulpmiddelen voor testen, deployen en migreren.

Voorbeelden:

- `run_tests.ps1`: draait de testsuite op Windows.
- `deploy_update.ps1` en `.cmd`: update/deploy flow.
- `deploy_vm.sh`: Linux/VM deploy.
- `migrate_res_company_exchange_rates.sql`: database-migratie voor exchange rates.

Scripts zijn handig, maar gebruik ze bewust. Lees eerst wat ze doen, vooral als
ze services stoppen, databases aanpassen of modules updaten.

## 19. Hoe de payrollberekening loopt

Een normale loonstrookflow:

1. Werknemer heeft een contract.
2. Contract heeft basisloon, salary type, valuta en vaste regels.
3. Loonrun of gebruiker maakt een loonstrook.
4. Loonstrook kiest de SR payroll structure.
5. Bij `compute_sheet()` bevriest de module relevante snapshots.
6. Odoo berekent salarisregels op sequence.
7. Salarisregels roepen Python helpers aan op `contract` en `payslip`.
8. Artikel 14 gebruikt de centrale calculator.
9. Regels worden opgeslagen in `hr.payslip.line`.
10. Bij bevestigen blijven snapshots en rapportagewaarden controleerbaar.
11. Fiscale rapportage leest bevestigde/betaalde loonstroken via SQL-view.

## 20. Waarom er een centrale calculator is

Payroll heeft een groot risico: dubbele berekeningen. Als de preview op contract
anders rekent dan de echte loonstrook, ontstaat verwarring en auditrisico.

Daarom is `sr_artikel14_calculator.py` een centrale plek voor Artikel 14. Dezelfde
logica wordt gebruikt door:

- contractpreview;
- loonstrookberekening;
- breakdown/uitleg;
- tests.

Dit is een goede architectuurkeuze.

## 21. Parameters en wettelijke wijzigingen

Fiscale waarden horen niet hardcoded verspreid te staan in veel bestanden.
Deze module gebruikt daarom parameters:

- `hr.rule.parameter` voor datumversies;
- `ir.config_parameter` voor live instellingen;
- defaults in de calculator als fallback.

De volgorde is:

1. expliciete `ir.config_parameter`;
2. `hr.rule.parameter` voor de relevante datum;
3. default in `sr_artikel14_calculator.py`;
4. foutmelding als er geen waarde is.

Als wetgeving verandert, moet je meestal niet direct de formule herschrijven.
Eerst kijk je:

- is het alleen een tarief?
- is het alleen een grens?
- is het een nieuwe schijf?
- is het een andere vrijstelling?
- is het echt een nieuwe berekeningsmethode?

Alleen het laatste vraagt meestal echte codewijziging.

## 22. Multi-currency en snapshots

Deze module ondersteunt SRD, USD en EUR.

Belangrijk principe: payroll wordt fiscaal in SRD berekend. Als een contract in
USD of EUR staat, wordt het loon naar SRD omgerekend met een wisselkoers.

Maar wisselkoersen veranderen. Daarom bevriest de loonstrook:

- contractvaluta;
- wisselkoers;
- netto bronvaluta;
- bruto bronvaluta;
- belastingvrije voet per periode;
- netto display mode.

Dit voorkomt dat oude loonstroken later andere bedragen tonen.

## 23. FN-loon versus maandloon

De module ondersteunt:

- maandloon: 12 periodes per jaar;
- FN-loon: 26 periodes per jaar.

Dit heeft invloed op:

- herleiding naar jaarloon;
- terugdeling naar periodebedrag;
- AOV;
- kinderbijslag;
- heffingskorting;
- validatie van periodes.

In `hr_payslip.py` staat een lijst met FN-periodes voor 2026. Dat voorkomt dat
een FN-loonstrook per ongeluk over een verkeerde periode wordt berekend.

## 24. Overwerk

Overwerk loopt via work entries en payslip inputs.

De flow:

1. Work entry registreert werkuren.
2. Module berekent geplande uren en extra uren.
3. Extra uren worden ingedeeld in 150% of 200%.
4. Validated work entries kunnen inputs op de loonstrook genereren.
5. Salarisregels gebruiken die inputs voor overwerkbedragen en belasting.

Feestdagen spelen mee bij 200% logica. Daarom bestaat `sr.public.holiday`.

## 25. Rapportages

Rapportages zijn verdeeld in:

- QWeb PDF-rapporten in `reports/`;
- list/pivot/form views in `views/hr_payroll_tax_report_views.xml`;
- CSV-export wizards;
- bankexport wizard.

Het fiscale overzicht is bewust read-only. Het is een auditrapport. Als het
rapport fout lijkt, moet je de onderliggende loonstrook of salarisregel corrigeren.

## 26. Hoe Odoo XML IDs gebruikt

XML-records hebben IDs zoals:

```xml
<record id="sr_payroll_structure" model="hr.payroll.structure">
```

Intern wordt dit:

```text
l10n_sr_hr_payroll.sr_payroll_structure
```

Dit heet een external ID of XML ID. Andere bestanden kunnen ernaar verwijzen:

```xml
<field name="struct_id" ref="l10n_sr_hr_payroll.sr_payroll_structure"/>
```

Belangrijke regels:

- XML IDs moeten uniek zijn binnen de module.
- Verander een bestaande XML ID niet zomaar.
- Als je een XML ID verwijdert, kunnen andere records breken.
- Als een record later nodig is, moet het eerder in het manifest geladen worden.

## 27. Hoe Odoo velden werken

Veelgebruikte veldtypes:

- `fields.Char`: tekst.
- `fields.Float`: kommagetal.
- `fields.Monetary`: bedrag met valuta.
- `fields.Integer`: geheel getal.
- `fields.Boolean`: ja/nee.
- `fields.Selection`: keuzeveld.
- `fields.Date`: datum.
- `fields.Datetime`: datum plus tijd.
- `fields.Many2one`: link naar een record.
- `fields.One2many`: meerdere records terug vanaf de andere kant.
- `fields.Many2many`: meerdere records aan beide kanten.
- `fields.Html`: HTML-inhoud.
- `fields.Binary`: bestand/export.

Computed fields hebben een compute-methode:

```python
sr_preview_netto = fields.Monetary(compute='_compute_sr_preview')
```

Onchange-methodes reageren in de UI voordat er opgeslagen wordt:

```python
@api.onchange('wage')
def _onchange_wage(self):
    ...
```

Constraints valideren bij opslaan:

```python
@api.constrains('wage')
def _check_non_negative_wage(self):
    ...
```

## 28. Belangrijke Odoo decorators

Je ziet vaak:

- `@api.depends(...)`: bepaalt wanneer computed fields opnieuw berekend worden.
- `@api.onchange(...)`: voert UI-logica uit wanneer een veld verandert.
- `@api.constrains(...)`: controleert geldigheid bij opslaan.
- `@api.model`: methode werkt op modelniveau.
- `@api.model_create_multi`: efficient meerdere records maken.
- `@api.ondelete(...)`: controle bij verwijderen.

Als je een dependency vergeet in `@api.depends`, kan een computed field niet
automatisch vernieuwen. Dat geeft stille fouten. Bij payroll is dat gevaarlijk.

## 29. Veelvoorkomende issues en oorzaken

### Module installeert niet

Mogelijke oorzaken:

- XML syntax fout.
- Verwijzing naar XML ID die nog niet bestaat.
- Python import ontbreekt.
- Access CSV verwijst naar verkeerd model.
- Modelnaam klopt niet.
- Security group bestaat nog niet.

### Veld verschijnt niet in de UI

Mogelijke oorzaken:

- Python-bestand niet geimporteerd.
- View XML niet in manifest.
- Module niet geupdate.
- View inheritance xpath klopt niet.
- Gebruiker heeft geen rechten.

### Berekening klopt niet

Mogelijke oorzaken:

- verkeerde salary rule sequence;
- bedrag zit in verkeerde category;
- positief/negatief teken verkeerd;
- parameterwaarde verkeerd;
- loonstrook gebruikt oude snapshot;
- contractvaluta of wisselkoers verkeerd;
- maandloon/FN verkeerd ingesteld;
- inputtype niet meegenomen.

### Rapport mist bedragen

Mogelijke oorzaken:

- SQL-view telt code niet mee;
- loonstrook is nog draft;
- salarisregelcode ontbreekt in query;
- multi-company rule filtert records;
- rapport gebruikt snapshotveld dat niet gevuld is.

### Access error

Mogelijke oorzaken:

- gebruiker mist payrollgroep;
- model mist access CSV;
- record rule blokkeert bedrijf;
- wizard heeft geen create-recht;
- controller controleert groep.

## 30. Checklist voordat je code wijzigt

Gebruik deze checklist bij elke wijziging.

1. Begrijp welk model geraakt wordt.
2. Zoek of er al bestaande helpermethodes zijn.
3. Controleer of het om contract, loonstrook, rapport of settings gaat.
4. Controleer of de wijziging een salarisregel raakt.
5. Controleer of parameters nodig zijn in plaats van hardcoded waarden.
6. Controleer of multi-currency geraakt wordt.
7. Controleer of FN-loon geraakt wordt.
8. Controleer of rapportages dezelfde code moeten meenemen.
9. Controleer security en access rights.
10. Schrijf of update tests.
11. Update de module in Odoo.
12. Draai tests.

## 31. Checklist voor nieuwe salarisregel

Bij een nieuwe salarisregel:

1. Kies een duidelijke code, bijvoorbeeld `SR_NIEUW`.
2. Kies een sequence op de juiste plek.
3. Kies de juiste category.
4. Bepaal of het bedrag bruto, inhouding, vrijgesteld of informatief is.
5. Bepaal of het op de loonstrook zichtbaar moet zijn.
6. Bepaal of het in `GROSS` moet vallen.
7. Bepaal of het in `NET` moet vallen.
8. Bepaal of rapportages het moeten optellen.
9. Voeg tests toe.
10. Update documentatie als het fiscaal belangrijk is.

## 32. Checklist voor nieuwe contractregel

Bij een nieuwe vaste contractregel:

1. Voeg eventueel een line type toe in `hr_contract_sr_line_type_data.xml`.
2. Kies een categorie:
   - `belastbaar`
   - `vrijgesteld`
   - `inhouding`
   - `aftrek_belastingvrij`
   - `fiscaal_grondslag`
3. Controleer hoe `hr_contract.py` die categorie oplost.
4. Controleer welke salarisregel de categorie gebruikt.
5. Voeg een test toe met contract, loonstrook en expected line totals.

## 33. Checklist voor nieuwe parameter

Bij een nieuwe parameter:

1. Voeg een `hr.rule.parameter` record toe als de waarde datumafhankelijk is.
2. Voeg eventueel een `ir.config_parameter` default toe als het via settings live
   instelbaar moet zijn.
3. Voeg mapping toe in `sr_artikel14_calculator.py` als de calculator hem gebruikt.
4. Voeg veld toe in `res_config_settings.py` als de gebruiker hem moet beheren.
5. Voeg hem toe aan de settings view.
6. Voeg validatie toe als negatieve waarden of verkeerde percentages gevaarlijk zijn.
7. Voeg tests toe.

## 34. Checklist voor rapportagewijziging

Bij een rapportagewijziging:

1. Bepaal of de data uit loonstrookregels of snapshotvelden moet komen.
2. Als het fiscale overzicht geraakt wordt, update `_query()` in
   `hr_payroll_tax_report.py`.
3. Update views als nieuwe velden zichtbaar moeten zijn.
4. Update CSV/PDF wizards als exports geraakt worden.
5. Controleer read-only gedrag.
6. Test met done/paid loonstroken, niet alleen draft.

## 35. Hoe je tests draait

Op Windows is er een script:

```powershell
.\scripts\run_tests.ps1
```

Dat script:

- controleert of de module geinstalleerd is;
- stopt de Odoo service;
- draait Odoo met `--test-enable`;
- leest de logfile;
- toont een samenvatting;
- start de service weer.

Je kunt ook Odoo handmatig starten met testopties, maar het script is makkelijker
voor deze installatie.

## 36. Hoe je gericht zoekt

Gebruik liever `rg` dan handmatig bladeren.

Voorbeelden:

```powershell
rg "SR_LB"
rg "sr_salary_type"
rg "hr.payroll.tax.report"
rg "action_export"
rg "_sr_artikel14_lb"
```

Als je wilt weten waar een salarisregelcode wordt gebruikt:

```powershell
rg "SR_KB_VRIJ"
```

Als je wilt weten waar een veld wordt getoond:

```powershell
rg "sr_aantal_kinderen"
```

## 37. Debug-denken in Odoo

Als iets fout gaat, vraag jezelf af:

1. Is dit een Python-fout, XML-fout, security-fout of data-fout?
2. Gebeurt het bij installatie, update, openen van scherm, opslaan of berekenen?
3. Is het record in de juiste company?
4. Is de gebruiker in de juiste groep?
5. Bestaat de XML ID?
6. Is het bestand opgenomen in het manifest?
7. Is het Python-bestand geimporteerd?
8. Is de module geupdate na wijziging?
9. Is de loonstrook draft of al bevestigd?
10. Zijn snapshots gevuld?

## 38. Waarom deze module niet alles in een bestand doet

Een payrollmodule kan snel groot worden. Alles in een bestand zetten zou de module
moeilijk testbaar en foutgevoelig maken.

Daarom is de code verdeeld:

- contractlogica bij contracten;
- loonstrooklogica bij loonstroken;
- parameters bij settings/rule parameters;
- rapportages bij rapportmodellen en wizards;
- views apart in XML;
- security apart;
- tests apart.

Deze structuur helpt om fouten te isoleren.

## 39. Wat je absoluut moet vermijden

Vermijd dit:

- XML IDs hernoemen zonder reden.
- Salary rule codes wijzigen zonder alle rapportages te updaten.
- Bedragen hardcoded in meerdere bestanden zetten.
- Een confirmed payslip opnieuw anders laten rekenen zonder auditreden.
- Multi-company security negeren.
- `sudo()` gebruiken zonder noodzaak.
- Rapportages direct wijzigbaar maken.
- Tests overslaan bij fiscale logica.
- Nieuwe Python-bestanden vergeten te importeren.
- Nieuwe XML-bestanden vergeten in `__manifest__.py`.
- Sequence van salarisregels wijzigen zonder volledige loonstrooktest.

## 40. Goede werkwijze voor een wijziging

Een veilige werkwijze:

1. Beschrijf de wijziging in gewone taal.
2. Zoek bestaande code die erop lijkt.
3. Pas zo weinig mogelijk bestanden aan.
4. Voeg een test toe die eerst zou falen.
5. Maak de codewijziging.
6. Update XML of security als nodig.
7. Update module in Odoo.
8. Draai tests.
9. Controleer de UI of het rapport.
10. Noteer wat gewijzigd is.

## 41. Leerroute voor deze module

Als je deze module echt wilt leren, lees in deze volgorde:

1. `__manifest__.py`
2. `README.md`
3. `models/hr_contract.py`
4. `models/sr_artikel14_calculator.py`
5. `data/hr_salary_rule_data.xml`
6. `models/hr_payslip.py`
7. `models/res_config_settings.py`
8. `models/hr_payroll_tax_report.py`
9. `views/hr_contract_views.xml`
10. `views/hr_payroll_tax_report_views.xml`
11. `wizard/` bestanden
12. `reports/` bestanden
13. `tests/test_article_14.py`
14. `tests/test_article_14_integration.py`
15. `tests/test_audit_fixes.py`

Deze volgorde werkt omdat je eerst de module-identiteit leert, dan de brondata,
dan de berekening, daarna de loonstrook, daarna rapportage en tests.

## 42. Kleine woordenlijst

- Add-on: Odoo module.
- ORM: Odoo-laag waarmee Python met database records werkt.
- Model: tabel plus gedrag.
- Record: een rij/object binnen een model.
- View: XML-definitie van een scherm.
- Action: opent scherm, wizard of rapport.
- Menuitem: menuoptie die naar een action verwijst.
- Wizard: tijdelijk popupmodel voor acties/export.
- QWeb: template engine voor rapporten en webpagina's.
- External ID/XML ID: vaste technische naam van een datarecord.
- Salary rule: salarisregel die Odoo berekent op een loonstrook.
- Category: groep waarin salarisregelbedragen optellen.
- Structure: set salarisregels voor een loonstrook.
- Payslip: loonstrook.
- Payslip run: batch loonstroken.
- Work entry: werk/afwezigheidsregel voor payroll.
- Snapshot: bevroren waarde op moment van berekening.
- Multi-company: meerdere bedrijven in een database.
- Access rights: lees/schrijf/maak/verwijder rechten.
- Record rule: filter welke records een gebruiker mag zien.

## 43. Samenvatting van jouw module in een zin

`l10n_sr_hr_payroll` is een Odoo 18 payroll-localisatie die Odoo's standaard
Payroll uitbreidt met Surinaamse contractvelden, fiscale parameters, salarisregels,
loonstrookberekeningen, overwerklogica, multi-currency snapshots, fiscale
rapportage, exports, PDF-rapporten, security en tests.

## 44. Belangrijkste mentale model

Onthoud dit:

```text
Contract -> Loonstrook -> Salarisregels -> Snapshots -> Rapportage
```

En voor techniek:

```text
Python model -> XML view/data -> Security -> Tests
```

Als je bij elke wijziging weet waar je zit in deze twee stromen, voorkom je de
meeste Odoo-issues.

## 45. Praktische eindcheck

Voordat je zegt dat iets klaar is:

1. Module update zonder fout.
2. Scherm opent zonder access error.
3. Loonstrook rekent.
4. Verwachte salary rule lines staan erop.
5. Netto klopt met formule.
6. Rapport toont dezelfde totals.
7. CSV/PDF export werkt als geraakt.
8. Multi-currency werkt als geraakt.
9. Maandloon en FN werken als geraakt.
10. Tests geven geen FAIL of ERROR.

Als deze lijst groen is, is de kans op issues veel kleiner.
