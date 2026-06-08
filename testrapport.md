Odoo 18 Salarisverwerking Module voor de Surinaamse Markt

Technisch Testrapport

| Documenttype: | Technisch testrapport |
| --- | --- |
| Module: | l10n_sr_hr_payroll |
| Versie: | 1.0 - Definitief |
| Datum: | 2 juni 2026 |
| Leerbedrijf: | Rosheuvel & Partners Business Group N.V. (RPBG) |
| Adres: | Verlengde Gemenelandsweg 151, Paramaribo |

# Projectinformatie

Dit rapport is opgesteld als onderdeel van de BPV bij Rosheuvel & Partners Business Group N.V. (RPBG). Het document sluit aan op Kerntaak 2 van de opleiding Applicatieontwikkelaar, in het bijzonder werkproces 2.3: Testen van applicaties. De testuitvoering is gericht op de Odoo-module `l10n_sr_hr_payroll`, een payrolllocalisatie voor Suriname bovenop Odoo 18 Enterprise.

| Onderdeel | Inhoud |
| --- | --- |
| Projectnaam | Odoo 18 Salarisverwerking Module voor de Surinaamse Markt |
| Moduleversie | 18.0.1.0 |
| Uitvoerder | Leonardo Lesley Legirin Ranoesendjojo |
| Opleiding | Applicatieontwikkelaar |
| BPV-docent | Mvr Varsha Sietaram |
| Praktijkopleider | Raveena Sewrattan |
| Opdrachtgever | Joan Heidanus |
| Stageperiode | 6 april 2026 - 25 juli 2026 |
| Testdatum | 2 juni 2026 |
| Testdatabase | Salarisverwerking-Module |
| Platform | Odoo 18 Enterprise op Windows |

# 1. Samenvatting

Voor werkproces 2.3 is de gerealiseerde salarisverwerkingmodule technisch getest op drie hoofdonderdelen uit het vaststellingsdocument: de salarisberekening, de volledige verwerking en de loonstrook als PDF. De testuitvoering is niet alleen gebaseerd op documentanalyse, maar ook op echte validaties in de lokale Odoo 18-omgeving van het project.

De kern van de module werkt aantoonbaar deels correct. Een module-update zonder testfouten in het laadproces is geslaagd, de kernberekening voor loonstroken is uitvoerbaar en een echte PDF-render van een SR-loonstrook leverde bruikbare PDF-bytes op. Tegelijkertijd is de geautomatiseerde regressieset niet volledig groen. De uitgevoerde tests tonen drie typen bevindingen: verouderde testverwachtingen rond kinderbijslag en fortnight-logica, een scopeverschil tussen de huidige basisloonvariant en de bredere rapportageverwachting uit projectdocumentatie, en een niet-blokkerende `wkhtmltopdf`-waarschuwing tijdens PDF-generatie.

Eindconclusie: de huidige modulevariant is technisch bruikbaar voor de basis van de salarisberekening en loonstrookgeneratie, maar nog niet volledig acceptabel voor de volledige projectscope zolang de regressietests en rapportagefunctionaliteit niet inhoudelijk zijn gelijkgetrokken met de actuele functionele scope.

# 2. Inleiding

## 2.1 Aanleiding en koppeling aan werkproces 2.3

In het vaststellingsdocument voor Kerntaak 2 staat bij werkproces 2.3 dat de gerealiseerde module getest moet worden op werking en correctheid. Daarbij moeten testscenario's worden opgesteld, testresultaten worden vastgelegd en moeten fouten worden opgelost of als verbetervoorstel worden beschreven. Als op te leveren producten worden onder andere een testrapport en gespreksverslagen genoemd.

Dit rapport geeft invulling aan dat werkproces. De uitvoering richt zich op de onderdelen die in de stageopdracht expliciet zijn genoemd:

- controle van de salarisberekening;
- controle van de volledige verwerkingsflow;
- controle van de loonstrook als PDF;
- vastlegging van bevindingen en verbetervoorstellen.

## 2.2 Doel van dit rapport

Dit rapport heeft vier doelen:

1. aantonen welke technische tests werkelijk zijn uitgevoerd;
2. vastleggen welke actieve fiscale baseline is gebruikt tijdens de test;
3. documenteren welke onderdelen slagen, falen of aandacht vragen;
4. onderbouwen welke vervolgacties nodig zijn voor acceptatie van de module.

# 3. Testbasis en afbakening

## 3.1 Testbasis

De testaanpak is opgesteld op basis van de volgende projectbronnen:

- het vaststellingsdocument Kerntaak 2 van Leonardo Ranoesendjojo;
- de technische documentatie over de gegevensstructuur;
- het bestaande projectrapport `RAPPORT_REALISATIEPROCES_ODOO_PROJECT.md`;
- het opgestelde testplan `TESTPLAN_SR_PAYROLL.md`;
- de actieve modulecode in `models/`, `reports/`, `data/` en `wizard/`;
- de bestaande regressietests in `tests/test_article_14.py`, `tests/test_article_14_integration.py` en `tests/test_report_exports.py`.

De belangrijkste technische controlepunten in de codebase zijn:

- centrale berekeningslogica in `models/sr_artikel14_calculator.py`;
- loonstrookverwerking in `models/hr_payslip.py`;
- scopeblokkades voor rapportages in `models/hr_payslip_run.py`;
- QWeb-lay-outs in `reports/report_payslip_sr.xml` en `reports/report_payslip_sr_layouts.xml`.

## 3.2 Afbakening

Dit testrapport richt zich op de actuele staat van de module zoals getest op 2 juni 2026 in de lokale ontwikkelomgeving. Buiten scope vallen performance-tests, security-audits en niet-gerelateerde fouten uit andere addons of uit de Windows-installatie van Odoo.

# 4. Testomgeving en actieve baseline

## 4.1 Testomgeving

De tests zijn uitgevoerd in de lokale ontwikkelomgeving van het project.

| Onderdeel | Waarde |
| --- | --- |
| Besturingssysteem | Windows |
| Odoo-versie | 18.0+e-20260407 |
| Python-runtime | Bundled Python van Odoo 18 |
| Database | Salarisverwerking-Module |
| Addonpad | sessions/addons/18.0/l10n_sr_hr_payroll |
| PDF-engine | wkhtmltopdf aanwezig op de Odoo-installatie |
| Test data-dir | `%TEMP%/odoo-test-data` |

De Odoo-commando's zijn uitgevoerd vanuit de servermap met de bundled Python-runtime. Tijdens de tests werd `--data-dir "$env:TEMP\odoo-test-data"` gebruikt om problemen met schrijfrechten onder `Program Files` te vermijden.

## 4.2 Vastgelegde fiscale baseline

Vooraf is de actieve fiscale baseline uit de huidige testdatabase uitgelezen. Dit is noodzakelijk omdat oudere documentatie, seeded XML-data en testverwachtingen niet overal dezelfde uitgangswaarden gebruiken.

| Parameter | Bron | Actieve waarde |
| --- | --- | --- |
| SR_BELASTINGVRIJ_JAAR | ir.config_parameter | 108000.0 |
| SR_FORFAITAIRE_PCT | ir.config_parameter | 0.04 |
| SR_FORFAITAIRE_MAX_JAAR | ir.config_parameter | 4800.0 |
| SR_SCHIJF_1_GRENS | ir.config_parameter | 42000.0 |
| SR_SCHIJF_2_GRENS | ir.config_parameter | 84000.0 |
| SR_SCHIJF_3_GRENS | ir.config_parameter | 126000.0 |
| SR_TARIEF_1 | ir.config_parameter | 0.08 |
| SR_TARIEF_2 | ir.config_parameter | 0.18 |
| SR_TARIEF_3 | ir.config_parameter | 0.28 |
| SR_TARIEF_4 | ir.config_parameter | 0.38 |
| SR_AOV_TARIEF | ir.config_parameter | 0.04 |
| SR_AOV_FRANCHISE_MAAND | ir.config_parameter | 400.0 |
| SR_HEFFINGSKORTING | ir.config_parameter | 0.0 |
| SR_KINDBIJ_MAX_KIND_MAAND | ir.config_parameter | 250.0 |
| SR_KINDBIJ_MAX_MAAND | ir.config_parameter | 1000.0 |
| Globale loonstrook-layout | ir.config_parameter | employee_simple |
| Bedrijfsloonstrook-layout | res.company.sr_payslip_template | employee_simple |

Deze baseline is leidend geweest bij de interpretatie van alle testuitkomsten in dit rapport.

# 5. Uitgevoerde testactiviteiten

## 5.1 Overzicht

| ID | Testactiviteit | Werkwijze | Resultaat |
| --- | --- | --- | --- |
| TV-01 | Module-load validatie | Odoo update zonder HTTP, met module-upgrade | Geslaagd |
| TV-02 | Kernberekening Artikel 14 | Gerichte regressietestklasse `TestArtikel14Berekening` | 8 geslaagd, 1 gefaald |
| TV-03 | Volledige verwerkingsflow | Gerichte integratietestklasse `TestIntegratieVolledigeCyclus` | 17 geslaagd, 3 gefaald |
| TV-04 | Rapportage en exports | Gerichte regressietestklasse `TestSrReportExports` | 6 geslaagd, 1 gefaald, 2 errors |
| TV-05 | PDF loonstrook spotcheck | Odoo shell, echte QWeb PDF-render | Geslaagd met waarschuwing |

## 5.2 Uitgevoerde commando's

De volgende technische controles zijn daadwerkelijk uitgevoerd:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
..\python\python.exe .\odoo-bin -c .\odoo.conf -d "Salarisverwerking-Module" -u l10n_sr_hr_payroll --stop-after-init --no-http --data-dir "$env:TEMP\odoo-test-data"
```

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
..\python\python.exe .\odoo-bin -c .\odoo.conf -d "Salarisverwerking-Module" -u l10n_sr_hr_payroll --test-enable --test-tags /l10n_sr_hr_payroll:TestArtikel14Berekening --stop-after-init --no-http --data-dir "$env:TEMP\odoo-test-data"
```

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
..\python\python.exe .\odoo-bin -c .\odoo.conf -d "Salarisverwerking-Module" -u l10n_sr_hr_payroll --test-enable --test-tags /l10n_sr_hr_payroll:TestIntegratieVolledigeCyclus --stop-after-init --no-http --data-dir "$env:TEMP\odoo-test-data"
```

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
..\python\python.exe .\odoo-bin -c .\odoo.conf -d "Salarisverwerking-Module" -u l10n_sr_hr_payroll --test-enable --test-tags /l10n_sr_hr_payroll:TestSrReportExports --stop-after-init --no-http --data-dir "$env:TEMP\odoo-test-data"
```

Daarnaast is een handmatige shell-spotcheck uitgevoerd waarbij een SR-loonstrook in PDF is gerenderd via de Odoo rapportengine.

# 6. Resultaten per testonderdeel

## 6.1 TV-01 Module-load validatie

De module-update zonder testmodus is geslaagd. Dat betekent dat de addon in de huidige database technisch kan laden, de manifeststructuur bruikbaar is en dat de basis van models, views en datarecords op dit moment geen blokkerende parse- of laadfouten oplevert.

Tijdens het laden verscheen wel een melding dat `hr_payroll_fleet` niet installable is en daarom wordt overgeslagen. Deze melding is niet direct aan de geteste payrollmodule toe te schrijven en is daarom als omgevingsruis behandeld.

Beoordeling: geslaagd.

## 6.2 TV-02 Kernberekening Artikel 14

De regressietestklasse `TestArtikel14Berekening` draaide 9 tests. Daarvan zijn 8 tests geslaagd en 1 test gefaald.

De gefaalde test was:

- `test_kinderbijslag_is_belastingvrij`

Waargenomen verschil:

- verwacht LB-bedrag: `-1928.0`
- werkelijk LB-bedrag: `-2308.0`

Interpretatie: de huidige testverwachting gaat uit van een volledig belastingvrije behandeling van kinderbijslag in dit scenario, terwijl de actuele module en testdatabase een andere fiscale uitkomst opleveren. Dit is geen bewijs dat de berekeningsengine volledig fout is, maar wel een duidelijke aanwijzing dat testverwachting, baseline of businessregel niet meer volledig op elkaar aansluiten.

Beoordeling: gedeeltelijk geslaagd.

## 6.3 TV-03 Volledige verwerkingsflow

De integratietestklasse `TestIntegratieVolledigeCyclus` draaide 20 tests. Daarvan zijn 17 tests geslaagd en 3 tests gefaald. Dit betekent dat het grootste deel van de end-to-end flow technisch nog werkt, maar dat er drie functionele afwijkingen zichtbaar zijn in fiscale randgevallen.

De drie gefaalde tests waren:

1. `test_fn_laatste_periode_corrigeert_jaartotaal_naar_maandloon`
2. `test_fortnight_maureen_like_netto_met_geprorateerde_aov_franchise`
3. `test_kinderbijslag_verhoogt_net_niet_lb`

Belangrijkste verschillen:

- Bij de FN-jaarcorrectie werd `174691.92` berekend waar de test `176736.0` verwachtte.
- Bij de fortnight AOV-berekening werd `346.46` berekend waar de test `300.92` verwachtte.
- Bij kinderbijslag week de loonbelasting opnieuw af: `-1928.0` versus `-2308.0`.

Interpretatie: de keten van contract, preview en loonstrook blijft uitvoerbaar, maar een deel van de oudere integratieverwachtingen sluit niet meer aan op de actuele implementatie en/of actuele fiscale baseline van de database.

Beoordeling: gedeeltelijk geslaagd.

## 6.4 TV-04 Rapportages en exports

De regressietestklasse `TestSrReportExports` draaide 9 tests. Daarvan zijn 6 tests geslaagd, 1 test gefaald en 2 tests met een error gestopt.

De twee errorgevallen waren:

- `CSV-export van fiscaal overzicht valt buiten de basisloon-scope van deze modulevariant.`
- `Belastingoverzicht per loonrun valt buiten de basisloon-scope van deze modulevariant.`

De gefaalde test was:

- `test_annual_statement_includes_overtime_tax_components_in_totals`

Daarbij ontbrak de verwachte `art 17c`-regel in het geteste totaaloverzicht.

Technische interpretatie: de code in `models/hr_payslip_run.py` blokkeert meerdere rapportageacties expliciet met een `UserError` die aangeeft dat deze functionaliteit buiten de basisloon-scope van de huidige modulevariant valt. Daardoor ontstaat een verschil tussen de bredere payroll- en rapportageverwachting uit de projectdocumentatie en de actuele functionele scope in de code.

Beoordeling: niet volledig geslaagd.

## 6.5 TV-05 PDF loonstrook spotcheck

Naast de regressietests is een handmatige technische spotcheck uitgevoerd op de QWeb PDF-render van een SR-loonstrook. Deze controle was bedoeld om vast te stellen of de rapportengine feitelijk PDF-bytes kan genereren voor een loonstrook in de actuele omgeving.

Resultaat van de spotcheck:

| Controlepunt | Waarde |
| --- | --- |
| Gegenereerde loonstrook-ID | 6476 |
| Aantal loonregels | 5 |
| Netto totaal | 17288.00 |
| PDF-bytes | 44273 |
| Content type | pdf |

Tijdens de render meldde `wkhtmltopdf` wel een `ContentNotFoundError`, maar de Odoo rapportengine genereerde desondanks een bruikbaar PDF-resultaat. De functionaliteit is daarom als geslaagd met waarschuwing beoordeeld.

Beoordeling: geslaagd met waarschuwing.

# 7. Bevindingen en verbetervoorstellen

## 7.1 Bevindingenoverzicht

| ID | Ernst | Bevinding | Onderbouwing | Verbetervoorstel |
| --- | --- | --- | --- | --- |
| BF-01 | Midden | Kinderbijslag-verwachting in regressietests sluit niet aan op actuele uitkomst. | Zowel unit- als integratietests falen op hetzelfde LB-verschil (`-1928.0` versus `-2308.0`). | Leg de gewenste fiscale behandeling van kinderbijslag opnieuw vast en pas daarna testverwachting of rekenlogica aan. |
| BF-02 | Midden | Fortnight/AOV/FN-jaarcorrectie tests gebruiken verouderde aannames. | Twee integratietests falen op FN-jaartotaal en geprorateerde AOV-franchise. | Bevestig de actuele businessregel voor FN in documentatie en code, en synchroniseer testdata, documentatie en calculator. |
| BF-03 | Hoog | Rapportage- en exportacties zijn in de huidige modulevariant bewust geblokkeerd. | `models/hr_payslip_run.py` gooit expliciet scopefouten voor run-overzicht, CSV-export en verwante rapportages. | Beslis formeel of de stage-oplevering een basisloonvariant of volledige payrollrapportagevariant moet tonen; verwijder daarna scopeblokkades of beperk de documentatie. |
| BF-04 | Laag | PDF-generatie geeft een `wkhtmltopdf`-waarschuwing, ondanks succesvolle output. | PDF-bytes worden gegenereerd, maar de render meldt `ContentNotFoundError`. | Controleer rapportassets, externe resources en stylingverwijzingen zodat PDF-render zonder waarschuwing verloopt. |

## 7.2 Analyse van de belangrijkste afwijking

De belangrijkste inhoudelijke bevinding is niet een harde crash, maar een verschil tussen drie waarheden binnen het project:

1. de actuele code in de module;
2. de actieve parameters in de gebruikte testdatabase;
3. de verwachtingen in oudere tests en documentatie.

Vooral bij kinderbijslag en fortnight-verloning zijn deze drie niet meer volledig gelijk. Daardoor geven de regressietests nu deels een rood resultaat, terwijl andere technische controles aantonen dat de module wel functioneert. Voor een betrouwbare acceptatie moet eerst worden vastgesteld welke waarheid leidend is: de huidige code, de huidige databaseconfiguratie of de oudere referentieberekeningen.

# 8. Conclusie

Op basis van de uitgevoerde tests kan worden geconcludeerd dat werkproces 2.3 inhoudelijk is uitgevoerd: de module is technisch getest op berekening, verwerking en PDF-uitvoer, en de resultaten zijn vastgelegd in een onderbouwd testrapport. De testuitvoering laat zien dat de kern van de loonverwerking operationeel is, maar dat de regressieset en de rapportagescope nog niet volledig in lijn zijn met de actuele projectverwachting.

Voor de basis van de salarisverwerking is het resultaat positief genoeg om te spreken van een technisch werkende modulevariant. Voor volledige acceptatie van de bredere stageopdracht is het resultaat nog voorwaardelijk. Eerst moeten de fiscale uitgangspunten formeel worden bevestigd, daarna moeten de regressietests worden bijgewerkt en moet een keuze worden gemaakt of rapportage-exports binnen of buiten de definitieve scope vallen.

# 9. Aanbevolen vervolgacties

1. Leg met praktijkopleider en opdrachtgever vast welke fiscale baseline officieel leidend is voor kinderbijslag, FN-AOV en FN-jaarcorrectie.
2. Werk daarna de geautomatiseerde tests bij zodat zij dezelfde businessregels controleren als de actuele modulevariant.
3. Beslis expliciet of de opgeleverde stagevariant een basisloonvariant of een volledige payrollrapportagevariant is, en pas code en documentatie daarop aan.
4. Controleer de rapporttemplate op ontbrekende assets of externe verwijzingen zodat de PDF-render zonder `wkhtmltopdf`-waarschuwing kan worden uitgevoerd.

# 10. Bespreekpunten voor gespreksverslag

Onderstaande punten kunnen direct worden gebruikt in een gespreksverslag met de praktijkopleider:

- bevestiging van de juiste fiscale behandeling van kinderbijslag in de testdatabase;
- bevestiging van de gewenste berekeningsregel voor fortnight AOV en jaarcorrectie;
- besluit over de scope van rapportages, jaaropgaven en CSV-exports in deze oplevering;
- akkoord op het feit dat de basis van de loonstrook-PDF technisch werkt, maar nog een renderwaarschuwing geeft.

# 11. Documenthistorie

| Versie | Datum | Wijziging |
| --- | --- | --- |
| 1.0 | 2 juni 2026 | Eerste volledige versie van het technisch testrapport op basis van werkelijk uitgevoerde Odoo-validaties. |