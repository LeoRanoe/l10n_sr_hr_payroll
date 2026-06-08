Odoo 18 Salarisverwerking Module voor de Surinaamse Markt

Acceptatietestplan

| Documenttype | Acceptatietestplan |
| --- | --- |
| Module | l10n_sr_hr_payroll |
| Versie | 1.0 |
| Datum | 3 juni 2026 |
| Organisatie | Rosheuvel & Partners Business Group N.V. (RPBG) |
| Testers | Jeady Mesir en Raveena Sewrattan |
| Testbegeleider | Leonardo Lesley Legirin Ranoesendjojo |

# 1. Testdoelstelling

De acceptatietest heeft als doel vast te stellen of de Odoo 18 salarisverwerking module in de praktijk bruikbaar is voor RPBG en of de belangrijkste payrolltaken binnen de afgesproken scope correct, begrijpelijk en controleerbaar kunnen worden uitgevoerd.

De test richt zich op drie hoofdvragen:

- kan een gebruiker de relevante payrollschermen en processen zonder onduidelijkheid gebruiken;
- levert de module logisch verklaarbare uitkomsten op voor contracten, loonstroken en PDF-uitvoer;
- is de huidige modulevariant acceptabel voor ingebruikname binnen RPBG.

De acceptatietest beoordeelt de functionele bruikbaarheid voor eindgebruikers. Deze test vervangt geen technische validatie, maar bouwt voort op de reeds uitgevoerde technische testronde.

# 2. Te testen functionaliteiten

De volgende functionaliteiten vallen binnen de acceptatiescope.

| ID | Functionaliteit | Prioriteit |
| --- | --- | --- |
| F-01 | Navigatie en toegangsrechten binnen Payroll en Suriname-configuratie | Hoog |
| F-02 | Invoer en opslag van contractgegevens in `Suriname Payroll -> Fiscale Data` | Hoog |
| F-03 | Contractpreview met bruto, loonbelasting, AOV en verwacht netto | Hoog |
| F-04 | Aanmaken en berekenen van een SR-loonstrook | Hoog |
| F-05 | Verwerking van vaste loonregels en variabele payslip-inputs | Hoog |
| F-06 | Fiscale verwerking van overwerk, bijzondere beloning en uitkering ineens | Midden |
| F-07 | FN-verloning en multi-currency verwerking | Midden |
| F-08 | PDF-loonstrook en leesbaarheid van de output | Hoog |
| F-09 | Rapportageacties en duidelijke scope- of foutmeldingen | Midden |

# 3. Testscenario's per functionaliteit

Per functionaliteit worden een normaalscenario en een foutscenario uitgevoerd.

## F-01 Navigatie en toegangsrechten

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Meld aan met een payrollgebruiker en open `Payroll -> Loonstroken -> Loonstroken SR`, `Payroll -> Configuratie -> Suriname -> SR Payroll Instellingen` en het contracttabblad `Suriname Payroll -> Fiscale Data`. |
| Foutscenario | Meld aan met een gebruiker zonder voldoende payrollrechten of open een scherm waarvoor rechten ontbreken. |
| Verwacht resultaat | De bevoegde gebruiker ziet de juiste schermen. Een onbevoegde gebruiker krijgt een duidelijke rechtenmelding en geen onverklaarbare fout. |

## F-02 Contractgegevens invoeren

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Maak of open een contract, vul loontype, basisloon, contractvaluta, aantal kinderen en vaste regels in en sla het contract op. |
| Foutscenario | Laat verplichte gegevens weg of voer een onlogische waarde in, zoals een onvolledig contract of een niet bruikbare fiscale invoer. |
| Verwacht resultaat | Een volledig contract wordt opgeslagen zonder onduidelijkheid. Onvolledige of onjuiste invoer wordt geblokkeerd of geeft een duidelijke waarschuwing. |

## F-03 Contractpreview controleren

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Open een volledig ingevuld contract en controleer of de preview bruto, loonbelasting, AOV en verwacht netto toont. |
| Foutscenario | Open een contract met ontbrekende fiscale gegevens of controleer of een onvolledig contract geen misleidende preview oplevert. |
| Verwacht resultaat | De preview geeft een begrijpelijke indicatie bij volledige data. Bij ontbrekende data blijft de gebruiker niet achter met een onverklaarbare of foutieve uitkomst. |

## F-04 SR-loonstrook aanmaken en berekenen

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Maak een loonstrook aan voor een werknemer met een geldig contract en bereken de loonstrook. |
| Foutscenario | Probeer een loonstrook te maken voor een werknemer zonder bruikbaar contract, met een foutieve periode of met ontbrekende payrollbasis. |
| Verwacht resultaat | Bij geldige gegevens wordt een bruikbare loonstrook berekend. Bij ongeldige gegevens volgt een duidelijke melding en geen stille fout. |

## F-05 Vaste regels en variabele inputs

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Gebruik een contract met vaste loonregels en voeg een variabele input toe, bijvoorbeeld een belastbare toelage of overwerkinput. Bereken daarna de loonstrook. |
| Foutscenario | Voeg een onjuiste input toe, gebruik een verkeerd inputtype of controleer of een ontbrekende input niet ongemerkt foutief wordt verwerkt. |
| Verwacht resultaat | De loonstrook neemt geldige vaste en variabele componenten correct over. Foute of onbruikbare invoer leidt niet tot een onverklaarbare salarisregel. |

## F-06 Overwerk, bijzondere beloning en uitkering ineens

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Verwerk een scenario met overwerk, een bijzondere beloning of een uitkering ineens en controleer of de loonstrook aparte fiscale regels toont. |
| Foutscenario | Controleer een situatie waarin de betreffende input ontbreekt, verkeerd geclassificeerd is of niet op de loonstrook verschijnt. |
| Verwacht resultaat | De gebruiker ziet dat deze posten herkenbaar en logisch worden verwerkt. Bij een afwijking is duidelijk dat het om een configuratie- of invoerprobleem gaat. |

## F-07 FN-verloning en multi-currency

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Bereken een FN-contract en, indien beschikbaar, een contract in USD of EUR. Controleer periodeherkenning, valutaweergave en netto-uitkomst. |
| Foutscenario | Controleer een FN- of vreemde-valutascenario met onlogische uitkomst, ontbrekende koers of onduidelijke AOV- of jaarcorrectie. |
| Verwacht resultaat | De uitkomst is voor de testers inhoudelijk uitlegbaar. Bij afwijkingen wordt minimaal een duidelijke melding of een bespreekpunt vastgelegd. |

## F-08 PDF-loonstrook

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Open een berekende loonstrook en genereer de PDF-loonstrook. Controleer naam, periode, inkomsten, inhoudingen en netto. |
| Foutscenario | Controleer of het rapport niet opent, onvolledig is of een onbruikbare layout toont. |
| Verwacht resultaat | De PDF opent en is leesbaar, volledig en bruikbaar voor HR of payroll. Een foutscenario is alleen acceptabel als er een duidelijke melding is en de oorzaak bekend is. |

## F-09 Rapportageacties en scopeberichten

| Onderdeel | Beschrijving |
| --- | --- |
| Normaalscenario | Open een beschikbare rapportageactie of probeer een actie die binnen deze modulevariant bewust beperkt is. |
| Foutscenario | De actie geeft een technische traceback, een onduidelijke fout of een afwijking die niet uitlegbaar is voor de gebruiker. |
| Verwacht resultaat | Een beschikbare rapportage opent correct. Als een actie buiten scope valt, krijgt de gebruiker een duidelijke functionele melding, bijvoorbeeld dat een overzicht buiten de basisloon-scope van deze modulevariant valt. |

# 4. Acceptatiecriteria

## 4.1 Wanneer is een scenario geslaagd

Een scenario is geslaagd wanneer:

- de gebruiker de handeling volledig kan uitvoeren binnen Odoo;
- de uitkomst logisch aansluit op de ingevoerde gegevens en de afgesproken payrollscope;
- foutscenario's leiden tot een duidelijke melding, blokkade of een expliciet bespreekpunt;
- er geen blokkerende fout optreedt waardoor de functionaliteit onbruikbaar wordt.

## 4.2 Wanneer is een scenario gezakt

Een scenario is gezakt wanneer:

- de functionaliteit niet uitvoerbaar is;
- de uitkomst aantoonbaar onjuist of onverklaarbaar is;
- de gebruiker een technische foutmelding krijgt zonder bruikbare uitleg;
- een hoog-prioriteitsscenario niet gebruikt kan worden voor de beoogde payrollhandeling.

## 4.3 Wanneer is de module geaccepteerd

De module kan als geaccepteerd worden beoordeeld wanneer:

- alle hoog-prioriteitsscenario's zijn geslaagd;
- eventuele midden-prioriteitsscenario's geen blokkerende impact hebben op de eerste loonverwerking;
- bekende scopebeperkingen vooraf zijn gecommuniceerd en door de testers acceptabel worden gevonden;
- Jeady Mesir en Raveena Sewrattan hun oordeel hebben vastgelegd.

Als er nog inhoudelijke open punten zijn, maar de kernfunctionaliteit wel bruikbaar is, kan de uitkomst `voorwaardelijk akkoord` zijn.

# 5. Rollen en verantwoordelijkheden

| Rol | Naam | Verantwoordelijkheden |
| --- | --- | --- |
| Tester 1 | Jeady Mesir, Software Consultant | Toetst technische en functionele bruikbaarheid, beoordeelt kwaliteit van de oplossing |
| Tester 2 | Raveena Sewrattan, Praktijkopleider | Toetst werkbaarheid in de praktijk, beoordeelt proces en gebruiksvriendelijkheid |
| Testbegeleider | Leonardo Lesley Legirin Ranoesendjojo | Bereidt testdata voor, begeleidt testuitvoering, noteert bevindingen en verwerkt feedback |
| Eventuele key-user | HR of payrollmedewerker RPBG | Geeft aanvullende praktijkfeedback als toekomstige gebruiker |

De testers voeren de scenario's uit of laten deze demonstreren, stellen verduidelijkende vragen en leggen per scenario vast of het resultaat acceptabel is.

# 6. Testomgeving beschrijving

De acceptatietest wordt uitgevoerd in een Odoo 18 Enterprise omgeving waarin de module `l10n_sr_hr_payroll` is geinstalleerd.

| Onderdeel | Omschrijving |
| --- | --- |
| Platform | Odoo 18 Enterprise |
| Besturingssysteem | Windows |
| Database | `Salarisverwerking-Module` of een functioneel gelijke testdatabase |
| Addon | `l10n_sr_hr_payroll` |
| Gebruikersrechten | Payrollrechten voor tester of testbegeleider |
| PDF-ondersteuning | Werkende Odoo PDF-render voor loonstroken |
| Testdata | Werknemers en contracten voor maandloon, FN, kinderbijslag, overwerk en vreemde valuta |

## 6.1 Bekende uitgangswaarden in de huidige testomgeving

| Onderdeel | Waarde |
| --- | --- |
| SR_BELASTINGVRIJ_JAAR | 108000.0 |
| SR_FORFAITAIRE_PCT | 0.04 |
| SR_FORFAITAIRE_MAX_JAAR | 4800.0 |
| SR_AOV_TARIEF | 0.04 |
| SR_AOV_FRANCHISE_MAAND | 400.0 |
| SR_HEFFINGSKORTING | 0.0 |
| Loonstrook-layout | `employee_simple` |

Deze waarden moeten vooraf worden bevestigd, zodat de testers weten welke baseline leidend is bij hun beoordeling.

# 7. Vastlegging van resultaten

| Functionaliteit | Status | Opmerking |
| --- | --- | --- |
| F-01 Navigatie en rechten |  |  |
| F-02 Contractgegevens invoeren |  |  |
| F-03 Contractpreview |  |  |
| F-04 SR-loonstrook berekenen |  |  |
| F-05 Vaste regels en variabele inputs |  |  |
| F-06 Overwerk, bijzondere beloning en uitkering ineens |  |  |
| F-07 FN-verloning en multi-currency |  |  |
| F-08 PDF-loonstrook |  |  |
| F-09 Rapportageacties en scopeberichten |  |  |

# 8. Eindbeoordeling

| Onderdeel | In te vullen |
| --- | --- |
| Datum uitvoering |  |
| Naam tester 1 | Jeady Mesir |
| Naam tester 2 | Raveena Sewrattan |
| Eindoordeel | Akkoord / Voorwaardelijk akkoord / Niet akkoord |
| Belangrijkste bevindingen |  |
| Actiepunten |  |

Dit acceptatietestplan is bedoeld om de module gestructureerd, praktisch en toetsbaar te beoordelen voordat RPBG overgaat tot definitieve ingebruikname.