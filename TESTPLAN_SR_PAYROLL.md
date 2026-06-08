# Testplan l10n_sr_hr_payroll

## 1. Documentgegevens

- Project: `l10n_sr_hr_payroll`
- Platform: Odoo 18 Enterprise
- Domein: Surinaamse salarisverwerking
- Versie document: 1.1
- Datum: 2026-06-02
- Status: bijgesteld na technische testronde
- Opsteller: GitHub Copilot op basis van repo-analyse en uitgevoerde Odoo-validaties

## 2. Doel van dit testplan

Dit testplan beschrijft hoe de module `l10n_sr_hr_payroll` wordt getest op werking, correctheid en volledigheid. De focus ligt op drie hoofdonderdelen:

1. controle van de salarisberekening;
2. controle van de volledige loonverwerkingsflow;
3. controle van de loonstrook als PDF.

Dit plan is op 2 juni 2026 bijgesteld op basis van het technische testrapport, zodat de testaanpak aansluit op de werkelijk uitgevoerde validaties, de actieve fiscale baseline van de gebruikte database en de actuele scope van de huidige modulevariant.

Het plan is bedoeld als uitvoerbaar document voor handmatige tests, als basis voor het testrapport en als onderbouwing voor gespreksverslagen over bevindingen, fouten en verbetervoorstellen.

## 3. Testobject

De test betreft de Odoo-module `l10n_sr_hr_payroll`, een uitbreiding op `hr_payroll` voor Surinaamse salarisverwerking. De module ondersteunt onder andere:

- loonbelasting volgens Artikel 14;
- bijzondere beloningen volgens Artikel 17;
- uitkering ineens volgens Artikel 17a;
- overwerk volgens Artikel 17c;
- AOV-bijdragen;
- maandloon en FN-verloning;
- vaste contractregels en variabele payslip-inputs;
- multi-currency verwerking in SRD, USD en EUR;
- contractpreview, loonstroken en PDF-uitvoer;
- fiscale overzichten en exports alleen voor zover deze in de huidige basisloon-scope variant beschikbaar zijn.

## 4. Testdoelen

De opdracht is correct uitgevoerd wanneer:

- alle geplande testscenario's zijn uitgevoerd en vastgelegd in het testrapport;
- de salarisberekeningen aantoonbaar overeenkomen met de vastgelegde Surinaamse fiscale parameters van de testdatabase;
- fouten zijn opgelost of als verbetervoorstel zijn beschreven met onderbouwing;
- de documentatie is bijgewerkt op basis van de testresultaten.

### Bijstelling na technische testronde 2026-06-02

De reeds uitgevoerde technische validatie heeft de volgende bijstellingen noodzakelijk gemaakt:

- de actieve databasebaseline is leidend en gebruikt nog legacywaarden zoals `SR_BELASTINGVRIJ_JAAR = 108000.0` en `SR_AOV_FRANCHISE_MAAND = 400.0`;
- de globale en bedrijfsloonstrook-layout zijn in de gebruikte database beide `employee_simple`;
- kinderbijslag en FN-verloning tonen in de huidige regressietests afwijkingen tussen testverwachting en actuele implementatie;
- run-level fiscale overzichten en CSV-exports zijn in de huidige modulevariant niet generiek beschikbaar, maar geven expliciete basisloon-scope foutmeldingen;
- PDF-generatie werkt technisch, maar gaf tijdens de testronde een niet-blokkerende `wkhtmltopdf`-waarschuwing.

## 5. Testbasis

Dit testplan is opgesteld op basis van:

- de modulecode in `models`, `reports`, `data` en `wizard`;
- bestaande regressietests in `tests/`;
- de functionele beschrijving in `README.md`;
- de projectbeschrijving in `RAPPORT_REALISATIEPROCES_ODOO_PROJECT.md`.

Belangrijke technische bronnen voor deze testaanpak zijn:

- centrale fiscale calculator in `models/sr_artikel14_calculator.py`;
- loonstrookopbouw in `models/hr_payslip.py`;
- salarisregels in `data/hr_salary_rule_data.xml`;
- PDF-layouts in `reports/report_payslip_sr.xml` en `reports/report_payslip_sr_layouts.xml`;
- regressietests in `tests/test_article_14.py`, `tests/test_article_14_integration.py`, `tests/test_report_exports.py`, `tests/test_currency_integration.py`, `tests/test_audit_fixes.py`, `tests/test_qa_audit_2026.py` en `tests/test_sr_vaste_regels.py`.

## 6. Afbakening

### In scope

- berekening van `BASIC`, `GROSS`, `SR_LB`, `SR_AOV`, `NET`;
- invloed van belastbare en vrijgestelde contractregels;
- invloed van payslip-inputs;
- heffingskorting voor zover actief in de testdatabase;
- AOV-berekening voor maandloon en FN;
- overwerk, bijzondere beloningen en uitkering ineens;
- contractpreview;
- volledige payslipflow;
- PDF-uitvoer van de loonstrook;
- technische validatie van rapportages en exports voor zover deze niet expliciet buiten de basisloon-scope zijn geplaatst;
- validaties en foutafhandeling die direct met payroll samenhangen.

### Buiten scope

- generieke Odoo-functionaliteit buiten deze module;
- infrastructurele storingen zoals PostgreSQL-serviceproblemen buiten de testopstelling;
- fouten uit niet-gerelateerde addons;
- run-level fiscale overzichten en CSV-exports die in de huidige modulevariant expliciet een basisloon-scope foutmelding teruggeven;
- performance- en loadtests;
- beveiligingsaudits buiten de functionele payrollscope.

## 7. Kritische randvoorwaarde: fiscale baseline eerst vastleggen

Voordat inhoudelijke tests worden uitgevoerd, moet eerst de actieve fiscale baseline van de testdatabase worden vastgelegd. Dit is verplicht, omdat er in deze repo oudere documentatie en oudere testgevallen voorkomen die niet overal dezelfde standaardwaarden gebruiken als de huidige implementatie.

Minimaal vast te leggen waarden:

- `SR_BELASTINGVRIJ_JAAR`
- `SR_FORFAITAIRE_PCT`
- `SR_FORFAITAIRE_MAX_JAAR`
- `SR_SCHIJF_1_GRENS`
- `SR_SCHIJF_2_GRENS`
- `SR_SCHIJF_3_GRENS`
- `SR_TARIEF_1`
- `SR_TARIEF_2`
- `SR_TARIEF_3`
- `SR_TARIEF_4`
- `SR_AOV_TARIEF`
- `SR_AOV_FRANCHISE_MAAND`
- `SR_HEFFINGSKORTING`
- `SR_KINDBIJ_MAX_KIND_MAAND`
- `SR_KINDBIJ_MAX_MAAND`
- gekozen payslip-layout

Leg per waarde ook vast:

- bron: `ir.config_parameter` of `hr.rule.parameter`;
- geldigheidsdatum;
- feitelijke waarde in de testdatabase;
- datum van vastlegging;
- naam van de tester.

### Baseline-tabel

| Parameter | Bron | Vastgelegde waarde | Geldig vanaf | Opmerking |
| --- | --- | --- | --- | --- |
| SR_BELASTINGVRIJ_JAAR | ir.config_parameter | 108000.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_FORFAITAIRE_PCT | ir.config_parameter | 0.04 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_FORFAITAIRE_MAX_JAAR | ir.config_parameter | 4800.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_SCHIJF_1_GRENS | ir.config_parameter | 42000.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_SCHIJF_2_GRENS | ir.config_parameter | 84000.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_SCHIJF_3_GRENS | ir.config_parameter | 126000.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_TARIEF_1 | ir.config_parameter | 0.08 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_TARIEF_2 | ir.config_parameter | 0.18 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_TARIEF_3 | ir.config_parameter | 0.28 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_TARIEF_4 | ir.config_parameter | 0.38 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_AOV_TARIEF | ir.config_parameter | 0.04 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_AOV_FRANCHISE_MAAND | ir.config_parameter | 400.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_HEFFINGSKORTING | ir.config_parameter | 0.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_KINDBIJ_MAX_KIND_MAAND | ir.config_parameter | 250.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| SR_KINDBIJ_MAX_MAAND | ir.config_parameter | 1000.0 | 2026-06-02 | Actieve databasewaarde tijdens testronde |
| Payslip-layout | ir.config_parameter / res.company | employee_simple | 2026-06-02 | Globale en bedrijfslayout waren gelijk |

## 8. Testomgeving

### Benodigde omgeving

- Odoo 18 Enterprise;
- database met geinstalleerde module `l10n_sr_hr_payroll`;
- PostgreSQL bereikbaar;
- gebruikersaccount met rechten voor payroll, configuratie en rapportage;
- mogelijkheid om PDF's te genereren;
- mogelijkheid om screenshots of exports als bewijs op te slaan.

### Aanbevolen testdatabase

- gebruik een aparte testdatabase;
- voer voor de test een module-update uit;
- zorg dat de database geen vervuiling bevat van oude conceptloonstroken voor dezelfde testpersonen;
- noteer de databasenaam in het testrapport.
- in de uitgevoerde technische testronde is de bestaande projectdatabase `Salarisverwerking-Module` gebruikt.

### Ondersteunende technische validatie

Ter ondersteuning van handmatige QA kan de addon-brede validatie worden gebruikt:

```powershell
.\python\python.exe .\server\odoo-bin -u l10n_sr_hr_payroll --test-enable -d "Salarisverwerking-Module" --stop-after-init --no-http --data-dir "$env:TEMP\odoo-test-data"
```

Deze opdracht vervangt het handmatige testplan niet, maar kan regressies sneller zichtbaar maken.

## 9. Testdata

Gebruik bij voorkeur vaste testprofielen, zodat bevindingen reproduceerbaar zijn.

### Aanbevolen werknemers en contracten

| Code | Profiel | Doel |
| --- | --- | --- |
| EMP-01 | maandloon zonder toelagen | basisberekening |
| EMP-02 | maandloon met belastbare toelagen | invloed op GROSS en LB |
| EMP-03 | maandloon met kinderbijslag | vrijgesteld versus belastbaar deel |
| EMP-04 | maandloon met pensioen of aftrek belastingvrij | Art. 10f effect op LB en AOV |
| EMP-05 | FN-contract | FN-berekening, periode-indicator en jaarequivalentie |
| EMP-06 | contract met overwerkrecht | work entries en overwerkinput |
| EMP-07 | contract in USD of EUR | valutaomrekening en koerssnapshot |
| EMP-08 | contract met bijzondere beloning | Artikel 17 en 17a |

### Aanbevolen variabele inputs

- overwerk 150%;
- overwerk 200%;
- vakantietoelage;
- gratificatie;
- bijzondere beloning;
- uitkering ineens;
- belastbare payslip-input;
- vrijgestelde payslip-input;
- inhouding als payslip-input.

## 10. Referentieformules voor handmatige controle

Gebruik voor handmatige herberekening altijd de actieve baseline uit hoofdstuk 7.

### Artikel 14 loonbelasting

1. `bruto_per_periode = basisloon + belastbare toelagen + belastbare kinderbijslag + belastbare inputs + fiscaal belastbare voordelen`
2. `aftrek_bv_per_periode = belastingvrije aftrek zoals pensioenpremie`
3. `adjusted_bruto_per_periode = bruto_per_periode - aftrek_bv_per_periode`
4. `bruto_jaar = bruto_per_periode * periodes`
5. `aftrek_bv_jaar = aftrek_bv_per_periode * periodes`
6. `adjusted_bruto_jaar = bruto_jaar - aftrek_bv_jaar`
7. `forfaitaire_jaar = min(adjusted_bruto_jaar * forfaitaire_pct, forfaitaire_max)`
8. `grondslag_belasting_jaar = adjusted_bruto_jaar - forfaitaire_jaar`
9. `belastbaar_jaarloon = max(0, grondslag_belasting_jaar - belastingvrij_jaar)`
10. pas de progressieve schijven toe op `belastbaar_jaarloon`
11. `lb_voor_heffingskorting_per_periode = lb_voor_heffingskorting_jaar / periodes`
12. `lb_per_periode = max(0, lb_voor_heffingskorting_per_periode - heffingskorting_per_periode)`

### AOV

De actuele implementatie moet leidend zijn boven verouderde documentatie.

- bij maandloon: `aov_grondslag = max(0, adjusted_bruto_per_periode - franchise_periode)`
- bij FN: `aov_grondslag = grondslag_belasting_per_periode`
- `aov_per_periode = aov_grondslag * aov_tarief`

### Netto

Voor de actuele module geldt als hoofdcontrole:

`netto = bruto_totaal - totaal_lb - totaal_aov - overige_inhoudingen - aftrek_bv`

Let op: heffingskorting mag niet als aparte pluspost dubbel in het netto terechtkomen.

## 11. Teststrategie

De testaanpak bestaat uit vijf lagen:

1. parameter- en uitgangscontrole;
2. handmatige functionele tests op salarisberekening;
3. ketentests van contract tot loonstrook en rapport;
4. regressiecontrole met bestaande geautomatiseerde tests en technische validatie;
5. interpretatie van afwijkingen tegen de actieve databasebaseline en de actuele basisloon-scope.

## 12. Scenario-overzicht

| ID | Onderdeel | Prioriteit | Verwachte uitkomst | Status na testronde 2026-06-02 |
| --- | --- | --- | --- | --- |
| TP-01 | fiscale baseline vastleggen | hoog | alle parameters en layout zijn aantoonbaar vastgelegd | uitgevoerd - geslaagd |
| TP-02 | maandloon onder grens | hoog | LB = 0 en AOV volgens actieve baseline | nog open |
| TP-03 | maandloon referentievoorbeeld | hoog | LB, AOV en netto volgen handmatige berekening | deels indirect gedekt |
| TP-04 | schijfgrenzen Art. 14 | hoog | juiste overgang per schijf zonder afrondingsfouten | nog open |
| TP-05 | belastbare toelagen | hoog | GROSS en LB nemen toe | nog open |
| TP-06 | kinderbijslag en vrijgestelde posten | hoog | netto stijgt, LB alleen op belastbaar deel | uitgevoerd - afwijking gevonden |
| TP-07 | aftrek belastingvrij en inhoudingen | hoog | LB en AOV dalen waar toegestaan, netto daalt correct | nog open |
| TP-08 | FN-verloning | hoog | juiste periodeherkenning, juiste LB/AOV, juiste jaarlogica | uitgevoerd - afwijking gevonden |
| TP-09 | overwerk Art. 17c | midden | juiste input, juiste classificatie, juiste LB/AOV op overwerk | nog open |
| TP-10 | bijzondere beloningen Art. 17 | hoog | juiste vrijstelling, juiste marginale belasting | nog open |
| TP-11 | uitkering ineens Art. 17a | hoog | aparte regels en correcte inhoudingen | nog open |
| TP-12 | multi-currency | midden | juiste conversie, juiste koerssnapshot | nog open |
| TP-13 | volledige loonverwerkingsflow | hoog | proces van contract tot goedkeuring werkt end-to-end | uitgevoerd - gedeeltelijk geslaagd |
| TP-14 | loonstrook PDF | hoog | alle informatie is volledig, juist en leesbaar | uitgevoerd - geslaagd met waarschuwing |
| TP-15 | rapportages en exports | midden | beschikbare rapporten werken; geblokkeerde acties geven expliciete scopefout | uitgevoerd - scopebeperking bevestigd |
| TP-16 | validaties en negatieve scenario's | midden | ongeldige invoer wordt geblokkeerd of correct gewaarschuwd | nog open |

Statusuitleg:

- `nog open`: nog niet als apart scenario vastgelegd in het testrapport;
- `deels indirect gedekt`: scenario is geraakt via regressietests, maar niet als los handmatig scenario uitgewerkt;
- `uitgevoerd - afwijking gevonden`: scenario is technisch getest en leverde een inhoudelijke mismatch op;
- `uitgevoerd - scopebeperking bevestigd`: de testronde bevestigde dat de huidige modulevariant hier bewust beperkingen heeft.

## 13. Uitwerking per testscenario

### TP-01 Fiscale baseline vastleggen

**Doel**

Vaststellen welke fiscale waarden en layout daadwerkelijk gelden in de testdatabase.

**Precondities**

- testdatabase is gekozen;
- module is geinstalleerd of geupdate;
- tester heeft configuratierechten.

**Stappen**

1. open de Suriname payrollinstellingen;
2. noteer alle parameters uit hoofdstuk 7;
3. controleer of waarden uit `ir.config_parameter` eventuele `hr.rule.parameter`-waarden overschrijven;
4. noteer de actieve payslip-layout;
5. voeg de waarden toe aan de baseline-tabel.

**Verwacht resultaat**

- alle testrelevante parameters zijn vastgelegd;
- duidelijk is welke bron leidend is;
- het testrapport kan later naar exact deze baseline verwijzen.

**Bewijs**

- screenshot instellingen;
- ingevulde baseline-tabel.

### TP-02 Maandloon onder belastinggrens

**Doel**

Controleren dat een laag maandloon geen positieve loonbelasting oplevert.

**Testdata**

- werknemer: `EMP-01`
- contracttype: maandloon
- loon: laag bedrag onder de actieve fiscale grens

**Stappen**

1. maak een contract zonder extra regels;
2. genereer een loonstrook voor een volledige maand;
3. voer een handmatige berekening uit op basis van de baseline;
4. vergelijk `GROSS`, `SR_LB`, `SR_AOV` en `NET` met de handmatige uitkomst.

**Verwacht resultaat**

- `SR_LB = 0` of gelijk aan de uitkomst van de handmatige berekening als de actieve baseline dit oplevert;
- `SR_AOV` volgt exact de actuele AOV-regel uit hoofdstuk 10;
- `NET` sluit aan op het totaal van de loonstrookregels.

### TP-03 Maandloon referentievoorbeeld

**Doel**

Stap voor stap bewijzen dat de hoofdformule voor een normaal maandloon klopt.

**Testdata**

- werknemer: `EMP-01`
- contracttype: maandloon
- voorbeeldloon: zelf te kiezen representatief bedrag uit de opdracht of de bestaande regressietests

**Stappen**

1. leg de gekozen parameterwaarden en het voorbeeldloon vast;
2. bereken handmatig bruto, adjusted bruto, forfaitaire aftrek, belastbaar jaarloon, LB en AOV;
3. maak de loonstrook aan;
4. controleer de waarden op de regels `BASIC`, `GROSS`, `SR_LB`, `SR_AOV`, `NET`;
5. controleer de breakdown in de PDF of HTML-preview.

**Verwacht resultaat**

- de loonstrook volgt exact dezelfde tussenstappen als de handmatige berekening;
- heffingskorting verlaagt uitsluitend de in te houden loonbelasting;
- netto is reproduceerbaar op centniveau.

### TP-04 Schijfgrenzen Artikel 14

**Doel**

Controleren dat overgangspunten tussen de belastingschijven correct worden verwerkt.

**Testdata**

Gebruik lonen die leiden tot een belastbaar jaarloon:

- net onder schijf 1;
- exact op schijf 1;
- net boven schijf 1;
- exact op schijf 2;
- exact op schijf 3;
- boven schijf 3.

**Stappen**

1. maak voor elk grensgeval een contract of pas het loon aan;
2. bereken per geval handmatig de verschuldigde belasting;
3. genereer per geval een loonstrook;
4. vergelijk de inhouding met de referentieberekening.

**Verwacht resultaat**

- elke schijf wordt alleen belast over het juiste deel van het inkomen;
- geen sprongen of onverklaarde afrondingsverschillen rond grensbedragen;
- de progressiviteit blijft intact.

### TP-05 Belastbare toelagen

**Doel**

Controleren dat belastbare contractregels en belastbare payslip-inputs correct doorwerken in `GROSS`, LB en AOV.

**Testdata**

- werknemer: `EMP-02`
- een contract met en zonder belastbare toelage;
- optioneel een belastbare payslip-input.

**Stappen**

1. maak een basiscontract zonder toelagen;
2. maak een vergelijkbaar contract met een belastbare toelage;
3. genereer voor beide een loonstrook;
4. vergelijk `GROSS`, `SR_LB`, `SR_AOV` en `NET`.

**Verwacht resultaat**

- `GROSS` stijgt met het bedrag van de belastbare toelage;
- LB en AOV nemen toe volgens de baseline;
- de toelage verschijnt correct op de loonstrook en in de PDF.

### TP-06 Kinderbijslag en vrijgestelde posten

**Doel**

Controleren dat vrijgestelde componenten het netto verhogen zonder onterecht de fiscale grondslag te verhogen.

**Testdata**

- werknemer: `EMP-03`
- contract met kinderbijslag;
- eventueel extra vrijgestelde toelage.

**Stappen**

1. maak een contract zonder kinderbijslag;
2. maak een vergelijkbaar contract met kinderbijslag;
3. genereer beide loonstroken;
4. controleer het verschil in `SR_KB_BELAST`, `SR_KB_VRIJ`, `SR_LB` en `NET`;
5. controleer de PDF-weergave.

**Verwacht resultaat**

- alleen het belastbare deel van kinderbijslag telt mee in de fiscale grondslag;
- het vrijgestelde deel verhoogt wel het netto;
- de loonstrook toont deze splitsing correct.
- als de regressietest een andere uitkomst laat zien, wordt dit niet direct als codefout geclassificeerd maar eerst als baseline- of businessregelafwijking vastgelegd.

### TP-07 Aftrek belastingvrij en overige inhoudingen

**Doel**

Controleren dat Art. 10f-aftrekken en overige inhoudingen correct worden verwerkt.

**Testdata**

- werknemer: `EMP-04`
- pensioenpremie of andere regel met categorie `aftrek_belastingvrij`;
- optioneel netto-inhouding zoals ziektekostenpremie.

**Stappen**

1. maak een contract met basisloon;
2. voeg een aftrek belastingvrij toe;
3. voeg optioneel een netto-inhouding toe;
4. genereer de loonstrook;
5. controleer handmatig de aangepaste grondslag voor LB en AOV;
6. controleer dat de inhouding ook zichtbaar is in het netto.

**Verwacht resultaat**

- `adjusted_bruto_per_periode` is lager dan `bruto_per_periode`;
- LB en AOV dalen conform de lagere grondslag;
- netto daalt tevens met het inhoudingsbedrag;
- de breakdown toont eerst aftrek belastingvrij en daarna, indien van toepassing, de franchise.

### TP-08 FN-verloning

**Doel**

Controleren dat FN-loonstroken correct worden berekend en gelabeld.

**Testdata**

- werknemer: `EMP-05`
- contracttype: `fn`
- geldige FN-periode van 14 dagen

**Stappen**

1. maak een FN-contract;
2. genereer een loonstrook voor een geldige FN-periode;
3. controleer `periodes = 26`, `fn_period_label` en `fn_period_indicator`;
4. voer handmatige herberekening uit met de actuele FN-regels uit hoofdstuk 10;
5. controleer de loonstrook en de PDF.

**Verwacht resultaat**

- de loonstrook wordt als FN herkend;
- de juiste periode-informatie wordt getoond;
- LB en AOV volgen de actuele FN-implementatie;
- ongeldige te lange periodes worden geweigerd.
- afwijkingen op FN-jaarcorrectie of geprorateerde AOV-franchise worden expliciet vastgelegd als open bespreekpunt zolang de definitieve businessregel niet is bevestigd.

### TP-09 Overwerk Artikel 17c

**Doel**

Controleren dat overwerk correct vanuit work entries of inputs op de loonstrook komt en correct wordt belast.

**Testdata**

- werknemer: `EMP-06`
- contract met overwerkrecht;
- overwerk 150% en 200%;
- optioneel een scenario zonder overwerkrecht.

**Stappen**

1. registreer overwerkuren of voeg de bijbehorende inputs toe;
2. genereer de loonstrook;
3. controleer of overwerkregels en bijbehorende LB/AOV-regels zijn aangemaakt;
4. voer een scenario uit zonder overwerkrecht;
5. controleer de uitkomst in rapportage en loonstrook.

**Verwacht resultaat**

- 150% en 200% overwerk worden correct geclassificeerd;
- de juiste belastingschijven voor Artikel 17c worden toegepast;
- zonder overwerkrecht ontstaat geen onterecht belastbaar overwerkbedrag.

### TP-10 Bijzondere beloningen Artikel 17

**Doel**

Controleren dat vakantietoelage, gratificatie en bijzondere beloningen met de juiste vrijstellingen en YTD-logica worden verwerkt.

**Testdata**

- werknemer: `EMP-08`
- input vakantietoelage;
- input gratificatie;
- input bijzondere beloning.

**Stappen**

1. maak een loonstrook met een of meer bijzondere beloningen;
2. controleer het vrijgestelde en belastbare deel;
3. controleer de aparte regels `SR_LB_BIJZ` en `SR_AOV_BIJZ`;
4. voer indien relevant een tweede loonstrook in hetzelfde jaar uit voor YTD-cap-controle.

**Verwacht resultaat**

- vrijstellingen worden correct toegepast;
- alleen het belastbare deel wordt marginaal belast;
- historische loonstroken van hetzelfde jaar worden correct meegenomen in cap-berekeningen.

### TP-11 Uitkering ineens Artikel 17a

**Doel**

Controleren dat een uitkering ineens apart wordt belast en zichtbaar is.

**Testdata**

- werknemer: `EMP-08`
- input `uitkering ineens`

**Stappen**

1. voeg een uitkering ineens toe op de loonstrook;
2. genereer de loonstrook;
3. controleer de regels `SR_LB_17A` en `SR_AOV_17A`;
4. controleer opname in totaalbedragen en rapportage.

**Verwacht resultaat**

- de aparte 17a-regels worden aangemaakt;
- bedragen volgen de actieve parameterwaarden;
- het bedrag is zichtbaar in de loonstrook en meegenomen in relevante rapporten.

### TP-12 Multi-currency

**Doel**

Controleren dat lonen en vaste regels in vreemde valuta correct naar SRD worden omgerekend en als snapshot worden vastgelegd.

**Testdata**

- werknemer: `EMP-07`
- contract in USD of EUR;
- mix van SRD- en vreemde-valutaregels.

**Stappen**

1. maak een contract in USD of EUR;
2. voeg vaste regels in dezelfde of andere toegestane valuta toe;
3. noteer de actieve wisselkoers;
4. genereer de loonstrook;
5. controleer basisloon, toelagen en netto in SRD;
6. controleer of de koers op de loonstrook is bevroren opgeslagen.

**Verwacht resultaat**

- bedragen worden correct omgerekend;
- de koers wordt consistent gebruikt in preview en payslip;
- incompatibele valutacombinaties worden geblokkeerd.

### TP-13 Volledige loonverwerkingsflow

**Doel**

Controleren dat de volledige payrollflow werkt van contract tot goedkeuring.

**Stappen**

1. maak of open een werknemer;
2. maak een contract aan met relevante vaste regels;
3. controleer de contractpreview;
4. maak een loonstrook;
5. voeg variabele inputs toe indien nodig;
6. voer `compute_sheet()` uit via de interface;
7. controleer alle salarisregels;
8. zet de loonstrook door naar de volgende status tot en met goedgekeurd of betaald, afhankelijk van de gebruikte workflow;
9. controleer dat de kern van de loonverwerkingsflow blijft werken;
10. registreer apart of aanvullende rapportages functioneel beschikbaar zijn of expliciet buiten scope zijn geplaatst.

**Verwacht resultaat**

- er ontstaan geen blokkades in het proces;
- alle verwachte regels zijn aanwezig;
- statusovergangen werken zonder inconsistenties;
- de loonstrook blijft reproduceerbaar na bevestiging.
- rapportageacties die in de huidige basisloon-variant bewust zijn geblokkeerd, tellen niet als flowbreuk maar als scopebevinding.

### TP-14 Loonstrook PDF

**Doel**

Controleren dat de loonstrook-PDF inhoudelijk correct, volledig en bruikbaar is.

**Controlepunten**

- bedrijfsnaam en werkgever-FIN;
- naam werknemer;
- personeelsnummer;
- CRIB-nummer;
- afdeling;
- functie;
- datum in dienst;
- bankrekening en banknaam;
- uurloon;
- periode en loonstrooknummer;
- inkomsten en inhoudingen;
- netto uit te betalen;
- correcte weergave van de gekozen layout;
- correcte detailweergave van LB- en AOV-opbouw in de uitgebreide layout;
- worked days en urenoverzicht als die gegevens aanwezig zijn.

**Stappen**

1. genereer een loonstrook voor een basisgeval;
2. exporteer de PDF in minimaal een standaardlayout;
3. controleer alle hierboven genoemde velden;
4. herhaal dit voor een loonstrook met bijzondere posten;
5. herhaal dit voor een FN-loonstrook;
6. controleer of heffingskorting niet dubbel als netto-pluspost verschijnt.

**Verwacht resultaat**

- alle verplichte gegevens zijn aanwezig;
- bedragen sluiten aan op de loonstrookregels;
- labels zijn begrijpelijk en consistent;
- de PDF is geschikt als controle- en communicatie-document.
- een technische renderwaarschuwing zonder verlies van PDF-output wordt als bevinding geregistreerd, niet automatisch als afkeur van het scenario.

### TP-15 Rapportages en exports

**Doel**

Controleren welke aanvullende rapportages in de huidige modulevariant functioneel beschikbaar zijn en welke expliciet buiten scope zijn geplaatst.

**Te testen onderdelen**

- fiscaal overzicht per run of periode;
- jaaropgave per werknemer;
- CSV-export van fiscale data;
- PDF-export van overzichtsrapporten.

**Stappen**

1. maak meerdere afgeronde loonstroken in het testjaar;
2. open het fiscaal overzicht;
3. registreer of de actie functioneel opent of een expliciete basisloon-scope foutmelding geeft;
4. als het rapport opent, controleer of alleen relevante afgeronde SR-loonstroken meetellen;
5. genereer waar mogelijk een jaaropgave;
6. controleer totals voor LB, AOV, bruto en netto;
7. exporteer waar mogelijk CSV en PDF;
8. controleer of overwerk, 17a en 17 correct zijn meegenomen.

**Verwacht resultaat**

- rapportages die in de huidige basisloon-variant beschikbaar zijn tonen alleen relevante loonstroken;
- totalen zijn optelbaar en herleidbaar voor de rapporten die daadwerkelijk openen;
- acties die bewust buiten scope staan geven een duidelijke basisloon-scope foutmelding;
- ontbrekende componenten zoals `art 17c` in totalen worden als bevinding geregistreerd.

### TP-16 Validaties en negatieve scenario's

**Doel**

Controleren dat de module ongeldige invoer correct blokkeert of van waarschuwingen voorziet.

**Te testen situaties**

- negatief loonbedrag;
- meer dan vier kinderen voor AKB;
- negatieve payslip-input;
- ongeldige FN-periode;
- contractwijziging terwijl niet-draft loonstroken bestaan;
- ongeldige valuta-invoer;
- shift langer dan 24 uur bij work entries.

**Verwacht resultaat**

- ongeldige situaties worden geblokkeerd of leveren een duidelijke waarschuwing op;
- geen stille datacorruptie;
- foutmeldingen zijn begrijpelijk genoeg voor beheer of payrollgebruikers.

## 14. Verwachte bewijsstukken per scenario

Per uitgevoerd scenario worden minimaal de volgende bewijsstukken vastgelegd:

- schermafbeelding van relevante invoer;
- schermafbeelding van berekende loonstrook;
- PDF-export indien van toepassing;
- terminal- of logoutput van de Odoo-validatie indien een scenario technisch is getest;
- handmatige referentieberekening in spreadsheet of bijlage;
- notitie van feitelijke parameterwaarden;
- bevindingen en afwijkingen.

## 15. Registratie van bevindingen

Gebruik voor bevindingen minimaal de volgende velden:

| Bevinding-ID | Scenario | Omschrijving | Ernst | Verwacht gedrag | Feitelijk gedrag | Status | Oplossing of voorstel |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BF-001 | | | | | | | |

Aanbevolen ernstniveaus:

- hoog: berekening of proces is juridisch of functioneel onjuist;
- midden: proces werkt, maar output of controleerbaarheid is onvolledig of foutgevoelig;
- laag: cosmetisch, label- of gebruiksprobleem zonder directe fiscale impact.

## 16. Testrapport: aanbevolen structuur

Het testrapport kan op basis van dit plan direct in de volgende vorm worden uitgewerkt:

1. doel van de testuitvoering;
2. gebruikte testomgeving en database;
3. vastgelegde fiscale baseline;
4. overzicht uitgevoerde scenario's;
5. resultaten per scenario;
6. overzicht bevindingen;
7. opgeloste fouten;
8. openstaande verbetervoorstellen;
9. conclusie of de opdracht voldoet aan het gewenste resultaat.

### Resultatentabel voor het testrapport

| Scenario | Uitgevoerd door | Datum | Resultaat | Bewijs | Opmerking |
| --- | --- | --- | --- | --- | --- |
| TP-01 | technische testronde | 2026-06-02 | geslaagd | baseline-tabel en shell-uitlezing | actieve databasebaseline vastgelegd |
| TP-02 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-03 | technische testronde | 2026-06-02 | deels gedekt | `TestArtikel14Berekening` | geen los handmatig referentiegeval uitgewerkt |
| TP-04 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-05 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-06 | technische testronde | 2026-06-02 | niet geslaagd | `TestArtikel14Berekening` en integratietest | kinderbijslagverwachting wijkt af |
| TP-07 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-08 | technische testronde | 2026-06-02 | niet geslaagd | `TestIntegratieVolledigeCyclus` | FN-AOV en jaarcorrectie wijken af |
| TP-09 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-10 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-11 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-12 |  |  | nog open |  | nog niet afzonderlijk uitgevoerd |
| TP-13 | technische testronde | 2026-06-02 | gedeeltelijk geslaagd | `TestIntegratieVolledigeCyclus` | 17/20 tests geslaagd |
| TP-14 | technische testronde | 2026-06-02 | geslaagd met waarschuwing | PDF-spotcheck | PDF-bytes gegenereerd, `wkhtmltopdf` gaf waarschuwing |
| TP-15 | technische testronde | 2026-06-02 | niet geslaagd / deels buiten scope | `TestSrReportExports` | run-overzicht en CSV-export bewust geblokkeerd |
| TP-16 |  |  | nog open |  | nog niet als los scenario uitgewerkt |

## 17. Gespreksverslagen: aanbevolen structuur

Omdat gespreksverslagen ook een opleverproduct zijn, wordt aanbevolen ieder overleg minimaal zo vast te leggen:

| Datum | Deelnemers | Onderwerp | Besproken bevinding | Besluit | Actiehouder | Deadline |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

Gebruik gespreksverslagen met name voor:

- interpretatie van wet- en regelgeving;
- afstemming over de juiste baseline;
- besluitvorming over gevonden fouten;
- afbakening tussen fout en verbetervoorstel;
- akkoord op bijgewerkte documentatie.

## 18. Exitcriteria

De testfase is afgerond wanneer:

- alle scenario's met prioriteit `hoog` zijn uitgevoerd;
- de salarisberekeningen zijn gecontroleerd tegen de vastgelegde baseline;
- de volledige loonverwerkingsflow is doorlopen;
- de loonstrook-PDF inhoudelijk is gecontroleerd;
- bevindingen zijn vastgelegd in een testrapport;
- openstaande afwijkingen zijn opgelost of verantwoord als verbetervoorstel;
- relevante documentatie is bijgewerkt.

Op basis van de testronde van 2026-06-02 zijn deze exitcriteria nog niet volledig bereikt, omdat TP-06, TP-08 en TP-15 inhoudelijke open punten hebben en meerdere hoog-prioriteitsscenario's nog niet afzonderlijk handmatig zijn vastgelegd.

## 19. Opmerking voor uitvoering

Bij elke handmatige referentieberekening moet de testdatabase leidend zijn. Als een waarde in ontwerpdocumentatie, README of oudere testgevallen afwijkt van de actieve configuratie in de database, dan moet die afwijking eerst worden vastgelegd voordat een scenario wordt beoordeeld als fout of niet fout.

Voor rapportageacties geldt aanvullend dat een expliciete basisloon-scope foutmelding in de huidige modulevariant eerst als scopebesluit moet worden beoordeeld voordat het scenario als functionele fout wordt geregistreerd.