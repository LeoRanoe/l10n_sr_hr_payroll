Odoo 18 Salarisverwerking Module voor RPBG

Implementatieplan

| Documenttype | Implementatieplan |
| --- | --- |
| Module | l10n_sr_hr_payroll |
| Versie | 1.0 |
| Datum | 3 juni 2026 |
| Organisatie | Rosheuvel & Partners Business Group N.V. (RPBG) |
| Opsteller | Leonardo Lesley Legirin Ranoesendjojo |

# 1. Inleiding en projectomschrijving

Dit implementatieplan beschrijft hoe de Odoo 18 module `l10n_sr_hr_payroll` gecontroleerd en beheerst in gebruik wordt genomen bij RPBG. De module is ontwikkeld als uitbreiding op de bestaande Odoo-omgeving en maakt het mogelijk om Surinaamse salarisverwerking uit te voeren binnen hetzelfde platform waarin medewerkersgegevens al worden beheerd.

De module ondersteunt de kern van de salarisverwerking voor de Surinaamse markt, waaronder:

- loonbelasting volgens Artikel 14;
- AOV-bijdragen;
- maandloon en fortnight-verloning;
- vaste looncomponenten en variabele payslip-inputs;
- bijzondere beloningen volgens Artikel 17;
- uitkering ineens volgens Artikel 17a;
- overwerk volgens Artikel 17c;
- contractpreview, loonstrookverwerking en PDF-loonstroken;
- multi-currency verwerking in SRD, USD en EUR;
- configureerbare payrollparameters binnen Odoo.

Het doel van de implementatie is om RPBG een beter beheersbaar, controleerbaar en minder foutgevoelig payrollproces te geven, zonder afhankelijk te blijven van losse handmatige tussenstappen buiten de bestaande Odoo-omgeving.

# 2. Huidige situatie versus nieuwe situatie

Volgens de stageopdracht gebruikt RPBG op dit moment Odoo al voor HR-functionaliteiten, zoals het beheren van medewerkers via het Employee Portal. Er is echter nog geen geintegreerde salarisverwerking binnen hetzelfde systeem. Daardoor vindt salarisverwerking nu buiten de standaard Odoo-flow plaats of is aanvullende handmatige verwerking nodig.

## Vergelijking

| Onderdeel | Huidige situatie | Nieuwe situatie met module |
| --- | --- | --- |
| HR-gegevens | Medewerkers staan in Odoo | Medewerkers en salarisverwerking zitten in dezelfde Odoo-omgeving |
| Salarisverwerking | Buiten Odoo of met handmatige stappen | Volledig in Odoo via contract, loonstrook en rapporten |
| Fiscale berekening | Afhankelijk van losse controles | Centrale en herhaalbare berekening via payrollregels en parameters |
| Invoer looncomponenten | Meer kans op handmatige fouten | Vaste regels op contract en variabele inputs op loonstrook |
| Controle | Lastiger te herleiden | Contractpreview, loonstrookregels en PDF-uitvoer geven controlepunten |
| Valuta | Niet eenduidig vastgelegd in payrollflow | Ondersteuning voor SRD, USD en EUR met koersvastlegging |
| Documentuitvoer | Mogelijk versnipperd | PDF-loonstrook rechtstreeks vanuit Odoo |
| Audit en beheer | Meer afhankelijk van losse documenten | Parameters, salarisregels en loonstroken zijn centraal vastgelegd |

De nieuwe situatie zorgt voor een meer uniforme werkwijze, minder dubbel werk en een duidelijker controleproces voor HR en payroll.

# 3. Technische implementatiestappen

De technische implementatie wordt in zes stappen uitgevoerd.

## 3.1 Voorbereiding van de omgeving

- Maak een volledige back-up van de Odoo-database en relevante filestore.
- Controleer of Odoo 18 Enterprise, PostgreSQL en de module `l10n_sr_hr_payroll` beschikbaar zijn op de doelomgeving.
- Bevestig vooraf welke scope live gaat: de basisloonvariant met loonstroken en PDF-uitvoer is leidend. Rapportages die in deze modulevariant bewust buiten scope zijn geplaatst, worden niet als live-functionaliteit gepresenteerd.
- Leg de fiscale baseline van de doelomgeving vast, waaronder belastingvrije voet, schijfgrenzen, tarieven, AOV-tarief en franchise.

## 3.2 Installatie of update van de module

- Plaats de module in het juiste addons-pad van Odoo.
- Voer een module-update uit via Odoo zodat modellen, views, data en beveiliging worden geladen.
- Controleer na de update of de Suriname-menu's zichtbaar zijn onder Payroll.
- Controleer of er geen parse-, laad- of toegangsrechtenfouten optreden.

## 3.3 Configuratie van payrollinstellingen

- Stel de `SR_*` payrollparameters in op de door RPBG bevestigde waarden.
- Controleer de salarisstructuur, loonregels, input types en loonstrook-layout.
- Controleer bedrijfsinstellingen zoals standaardlayout en toegangsrechten voor payrollgebruikers.
- Bevestig welke rapportageacties beschikbaar moeten zijn in de productievariant.

## 3.4 Voorbereiden van stamgegevens en testdata

- Controleer werknemersgegevens en contracten op volledigheid.
- Vul per contract het loontype in: maandloon of fortnight.
- Leg contractvaluta vast in SRD, USD of EUR waar van toepassing.
- Richt vaste loonregels in voor structurele toelagen en inhoudingen.
- Bereid voorbeeldmedewerkers voor voor maandloon, FN-verloning, kinderbijslag, overwerk en vreemde valuta.

## 3.5 Functionele controle en acceptatietest

- Voer per kernscenario een controle uit op contractpreview, loonstrookberekening en PDF-uitvoer.
- Laat de acceptatietest uitvoeren door Jeady Mesir en Raveena Sewrattan.
- Registreer afwijkingen, beslispunten en eventuele scopebeperkingen.
- Verwerk noodzakelijke correcties voordat livegang wordt goedgekeurd.

## 3.6 Productie-inname en nazorg

- Maak vlak voor livegang opnieuw een back-up.
- Voer de definitieve update uit op de productieomgeving.
- Start met een eerste gecontroleerde loonperiode of pilotgroep.
- Houd in de eerste verwerkingscyclus extra ondersteuning beschikbaar voor HR en payroll.
- Evalueer na de eerste loonrun de werking, foutmeldingen en gebruikerservaring.

# 4. Organisatorische aanpak

De implementatie vraagt niet alleen technische installatie, maar ook duidelijke taakverdeling en afstemming.

| Rol | Verantwoordelijkheden | Moment |
| --- | --- | --- |
| Applicatieontwikkelaar | Module opleveren, installeren, configureren, issues analyseren en documentatie bijwerken | Voorbereiding, testfase, nazorg |
| Jeady Mesir - Software Consultant | Technische review, functionele toetsing, advies over kwaliteit en livegang | Tijdens controle en acceptatie |
| Raveena Sewrattan - Praktijkopleider | Procesbegeleiding, functionele beoordeling, bewaken van werkafspraken en oplevering | Tijdens hele traject |
| HR of payrollgebruiker van RPBG | Aanleveren van praktijkinformatie, uitvoeren van gebruikerscontroles, bevestigen of de uitkomst werkbaar is | Testfase en eerste loonrun |
| Systeembeheer of Odoo-beheerder | Databaseback-up, toegangsrechten, beschikbaarheid van productieomgeving | Voor en tijdens livegang |
| Opdrachtgever of proceseigenaar | Beslissen over scope, akkoord op livegang, prioriteren van open punten | Voor go/no-go besluit |

De organisatorische aanpak is gefaseerd. Eerst worden de technische randvoorwaarden bevestigd, daarna worden stamgegevens en instellingen gecontroleerd, vervolgens wordt een acceptatietest uitgevoerd en pas daarna vindt livegang plaats.

# 5. Planning en tijdlijn

Onderstaande planning is een realistische invoeringsplanning voor een gecontroleerde implementatie. De exacte datums kunnen door RPBG worden ingevuld.

| Fase | Periode | Activiteiten | Resultaat |
| --- | --- | --- | --- |
| Fase 1 Voorbereiding | Week 1 | Back-up, scope bevestigen, baseline vastleggen, omgeving controleren | Implementatie gereed voor configuratie |
| Fase 2 Configuratie | Week 1 | Module-update, payrollparameters instellen, rechten en layouts controleren | Werkende testomgeving |
| Fase 3 Datacontrole | Week 2 | Contracten controleren, vaste regels invullen, voorbeeldmedewerkers inrichten | Betrouwbare testdata |
| Fase 4 Acceptatietest | Week 2 | Gebruikersscenario's uitvoeren met Jeady Mesir en Raveena Sewrattan | Go/no-go advies |
| Fase 5 Correctieronde | Week 3 | Open punten oplossen of formeel afbakenen | Definitieve oplevervariant |
| Fase 6 Livegang en nazorg | Week 3 en 4 | Productie-update, eerste loonrun begeleiden, gebruikers ondersteunen | Module in gebruik bij RPBG |

Als RPBG sneller wil invoeren, kunnen fase 2 en fase 3 deels parallel lopen. Dat is alleen verantwoord als de fiscale baseline vooraf definitief is bevestigd.

# 6. Risico's en maatregelen

| Risico | Gevolg | Maatregel |
| --- | --- | --- |
| Onjuiste fiscale baseline in productie | Verkeerde loonbelasting of AOV-berekening | Voor livegang alle `SR_*` parameters formeel laten bevestigen en vastleggen |
| Onvolledige contractgegevens | Onjuiste loonstroken of lege previews | Contractchecklist gebruiken en alleen volledige contracten meenemen in de eerste loonrun |
| Verwachtingsverschil over rapportagescope | Gebruikers verwachten functies die in deze variant bewust geblokkeerd zijn | Scope vooraf communiceren en in training benoemen welke rapportages wel en niet live gaan |
| Onvoldoende gebruikerskennis | Fouten bij invoer of interpretatie van loonstroken | Korte instructie en begeleide eerste verwerkingsronde organiseren |
| Fouten bij productie-update | Tijdverlies of verstoring van payrollproces | Eerst testen op aparte testdatabase, daarna pas productie-update uitvoeren |
| Wisselkoersen of valuta niet correct ingesteld | Afwijkende netto- of rapportagebedragen | Multi-currency contracten vooraf apart controleren en koersbron vastleggen |
| Open punten uit acceptatietest blijven onbeheerd | Onzekerheid bij livegang | Bevindingenlijst met eigenaar, deadline en besluit per punt bijhouden |

# 7. Communicatieplan richting medewerkers

Goede communicatie voorkomt onduidelijkheid tijdens invoering. Niet iedere medewerker hoeft de volledige technische werking te kennen, maar iedereen moet weten wat verandert en wat daarvan de praktische gevolgen zijn.

| Doelgroep | Boodschap | Kanaal | Moment | Verantwoordelijke |
| --- | --- | --- | --- | --- |
| HR en payrollmedewerkers | Uitleg over nieuwe werkwijze in Odoo, invoer van contractgegevens, loonstroken en controles | Korte instructiesessie en handleiding | Voor acceptatietest en voor livegang | Applicatieontwikkelaar en praktijkopleider |
| Leidinggevenden | Doel, planning, risico's en go/no-go momenten | Kort voortgangsoverleg | Aan begin en voor livegang | Opdrachtgever of proceseigenaar |
| Testers | Testscope, testscenario's, beslispunten en verwachte uitkomsten | Acceptatietestplan en testoverleg | Vlak voor testuitvoering | Applicatieontwikkelaar |
| Medewerkers die loonstroken ontvangen | Aankondiging dat loonstroken vanuit Odoo worden verwerkt of anders worden aangeleverd | Interne mededeling of e-mail | Kort voor eerste live loonrun | HR of payroll |
| Beheer en ondersteuning | Technische wijziging, back-upmoment, supportvenster en escalatieroute | Technisch overleg of ticketsysteem | Voor update en tijdens nazorg | Odoo-beheerder |

De communicatie moet steeds drie punten bevatten:

- wat er verandert;
- vanaf wanneer het verandert;
- bij wie vragen of afwijkingen gemeld moeten worden.

# 8. Afronding en succescriteria

De implementatie is succesvol wanneer aan de volgende voorwaarden is voldaan:

- de module is zonder technische fouten geinstalleerd of geupdate;
- de afgesproken payrollparameters zijn gecontroleerd en vastgelegd;
- de belangrijkste contract- en loonstrookscenario's zijn succesvol getest;
- Jeady Mesir en Raveena Sewrattan hebben de acceptatietest uitgevoerd en beoordeeld;
- open punten zijn opgelost of expliciet als bekende beperking geaccepteerd;
- HR en payroll weten hoe zij de module in de eerste loonperiode moeten gebruiken.

Met dit implementatieplan kan RPBG de module stapsgewijs, gecontroleerd en met beperkte verstoring invoeren binnen de bestaande Odoo-omgeving.