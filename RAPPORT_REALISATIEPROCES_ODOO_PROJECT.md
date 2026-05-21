# Rapport Realisatieproces Odoo Project

## Projectgegevens

- Project: l10n_sr_hr_payroll
- Platform: Odoo 18 Enterprise
- Basis: uitbreiding op de standaardmodule `hr_payroll`
- Domein: Surinaamse salarisverwerking en fiscale rapportage
- Doel: het realiseren van een onderhoudbare payrollmodule die de Wet Loonbelasting Suriname ondersteunt binnen de bestaande Odoo-architectuur

## Inleiding

Binnen dit project is gewerkt aan de Odoo-module `l10n_sr_hr_payroll`. Deze module is ontwikkeld als functionele uitbreiding op de standaard payrollomgeving van Odoo 18. Het project richt zich op de verwerking van Surinaamse salarisadministratie en ondersteunt onder andere loonbelasting volgens Artikel 14, bijzondere beloningen volgens Artikel 17, uitkering ineens volgens Artikel 17a, overwerk volgens Artikel 17c, AOV-bijdragen, contractspecifieke looncomponenten, rapportages, wizards en configuratie van fiscale parameters.

Het realisatieproces bestond niet alleen uit programmeren, maar ook uit het analyseren van de bestaande Odoo-structuur, het vertalen van wet- en regelgeving naar concrete applicatielogica, het inventariseren van interfaces, het ontwerpen van ergonomisch verantwoorde schermen en het documenteren van de oplossing. In dit rapport wordt dat realisatieproces inhoudelijk beschreven aan de hand van concrete voorbeelden uit het project.

## 1. Analyse van functioneel en technisch ontwerp

Aan het begin van het project is eerst onderzocht welke functionele en technische uitgangspunten bepalend waren voor de realisatie. Functioneel gezien moest de module loonverwerking mogelijk maken volgens Surinaamse wetgeving, met voldoende flexibiliteit om tarieven, vrijstellingen en schijven later aanpasbaar te houden. Technisch gezien moest de oplossing passen binnen de standaard architectuur van Odoo 18, zodat de module niet los van het platform zou functioneren maar juist als aanvulling op bestaande payrollprocessen.

In deze analyse is specifiek gekeken naar de bestaande Odoo-modellen en hoe deze gebruikt of uitgebreid konden worden. De belangrijkste analysepunten waren:

- `hr.contract` als bron voor basisloon, loontype, vaste loonregels, valuta en fiscale contractgegevens;
- `hr.payslip` en `hr.payslip.line` als basis voor de uiteindelijke loonstrookberekening;
- `hr.payslip.input` en `hr.payslip.input.type` voor variabele posten zoals overwerk, bonus en vakantietoelage;
- `hr.rule.parameter` en instellingen op bedrijfsniveau voor het opslaan van fiscale parameters zoals tarieven, schijfgrenzen en vrijstellingen;
- QWeb-rapporten en wizardmodellen voor jaaropgaven, overzichten en PDF-export;
- PostgreSQL als basis voor een auditvriendelijke SQL-view voor fiscale rapportage.

Tijdens de analyse is vastgesteld dat de fiscale logica niet hardcoded mocht worden vastgelegd in losse schermen of verspreide berekeningen. Daarom is gekozen voor een opzet waarbij fiscale waarden configureerbaar zijn en waarbij rekenlogica centraal wordt gebruikt. Ook is vastgesteld dat de contractpreview en de daadwerkelijke loonstrookberekening zo veel mogelijk dezelfde grondslag moesten delen, om verschillen tussen verwachting en daadwerkelijke verwerking te voorkomen.

Een tweede belangrijk analysepunt was de ondersteuning van meerdere verloningstypen. De module moest zowel maandloon als fortnight-verloning ondersteunen. Dat betekende dat het systeem niet alleen een vast maandloon moest kunnen verwerken, maar ook automatisch bedragen per periode moest kunnen herrekenen op basis van `12` of `26` betaalmomenten per jaar. Dit had invloed op contractvelden, validaties, de loonstrooklogica en de rapportages.

Daarnaast zijn ergonomie-eisen meegenomen in de analyse. Binnen Odoo betekent ergonomie vooral dat schermen logisch zijn ingedeeld, dat irrelevante velden niet onnodig zichtbaar zijn, dat waarschuwingen op het juiste moment worden gegeven en dat payrollmedewerkers zonder onnodige technische kennis met de module kunnen werken. Dit is nadrukkelijk meegenomen bij de vormgeving van contracttabbladen, configuratieschermen, zoekfilters en wizardstappen.

## 2. Eigen maken van programmeertaal, framework en methodieken

Voor het realiseren van deze opdracht was het nodig om de gebruikte programmeertaal en ontwikkelmethodieken in voldoende mate te beheersen. Binnen dit project betekende dat niet alleen werken met Python, maar ook met de manier waarop Odoo modules opbouwt, uitbreidt en integreert.

De applicatieontwikkelaar heeft zich in dit project verdiept in:

- Python voor modeluitbreidingen, validaties, rekenlogica en business rules;
- XML voor views, menu's, acties, helpteksten, security en initiële data;
- QWeb voor de opmaak van loonstroken, overzichten en jaaropgaven;
- PostgreSQL en SQL-viewconstructies voor auditrapportage;
- de Odoo ORM, inheritance, computed fields, onchange-methoden, constraints en transient models.

De toegepaste methodiek was sterk modulair. In plaats van een monolithische implementatie is de oplossing opgesplitst in modellen, wizardbestanden, rapportdefinities, configuratieschermen, datarecords en beveiligingsbestanden. Deze aanpak sluit aan op de Odoo-manier van werken en maakt het mogelijk om onderdelen later te onderhouden of uit te breiden zonder de hele module opnieuw te moeten opzetten.

Een concreet voorbeeld hiervan is dat de contractlogica, rapportlogica en configuratielogica niet in een enkel bestand zijn geplaatst, maar zijn verdeeld over aparte modellen en views. Daardoor kon bijvoorbeeld het contractformulier worden uitgebreid zonder de rapportagecode te vermengen met de schermlogica. Dat is niet alleen technisch netter, maar vergroot ook de leesbaarheid en overdraagbaarheid van de code.

## 3. Inventarisatie van interfaces

Voordat de applicatie volledig is gerealiseerd, zijn de interfaces en koppelingen geïnventariseerd die voor de opdracht relevant waren. Binnen dit project ging het vooral om interne interfaces tussen bestaande Odoo-componenten en nieuw ontwikkelde functionaliteit.

De belangrijkste interfaces zijn:

- de interface tussen contractgegevens en loonstrookberekening;
- de interface tussen vaste contractregels en fiscale categorisering;
- de interface tussen payrollinstellingen en de gebruikte fiscale rekenwaarden;
- de interface tussen loonstroken en fiscale rapportages;
- de interface tussen work entries, overwerkclassificatie en payslip inputs;
- de interface tussen contractvaluta, wisselkoersen en SRD-verwerking.

Deze inventarisatie heeft geleid tot een aantal concrete ontwerpkeuzes.

Ten eerste is `hr.contract` uitgebreid met Suriname-specifieke velden zoals `sr_salary_type`, `sr_contract_currency`, `sr_aantal_kinderen` en `sr_vaste_regels`. Daarmee werd het contract het centrale startpunt voor de payrollverwerking. Vanuit het contract wordt bepaald of iemand in maandloon of fortnight-verloning valt, in welke valuta het loon is vastgelegd en welke vaste toelagen of inhoudingen structureel moeten terugkomen.

Ten tweede is de koppeling naar payslipverwerking uitgewerkt via salarisregels en inputs. Variabele componenten zoals overwerk of eenmalige toelagen worden niet in het contract opgeslagen, maar via `hr.payslip.input.type` en de loonstrook zelf verwerkt. Hierdoor bleef het onderscheid tussen vaste en variabele looncomponenten helder.

Ten derde is de interface naar instellingen vormgegeven via gefilterde Suriname-specifieke schermen bovenop bestaande Odoo-modellen. In plaats van gebruikers alle algemene payrollparameters te tonen, is een eigen configuratielaag gemaakt voor `SR_*`-parameters, vaste looncodes en eenmalige looncodes. Deze keuze verbeterde zowel het beheer als de gebruiksvriendelijkheid.

Ten vierde is de rapportage-interface ingericht via een aparte SQL-view in het model `hr.payroll.tax.report`. Daarmee wordt fiscale data niet handmatig overgenomen, maar rechtstreeks opgebouwd vanuit bevestigde loonstroken. Dit ondersteunt auditbaarheid en maakt filters per loonrun, afdeling, contractvaluta en bedrijf mogelijk.

## 4. Realisatie van de applicatie

Na de analyse en inventarisatie is gestart met de feitelijke realisatie van de applicatie. Deze realisatie is opgesplitst in verschillende lagen binnen de module.

### 4.1 Uitbreiding van contract- en stamgegevens

Het contractformulier is uitgebreid met een apart tabblad voor Suriname Payroll. Binnen dat tabblad zijn onder andere de volgende onderdelen gerealiseerd:

- keuze tussen maandloon en fortnight-verloning;
- ondersteuning van contractvaluta in SRD, USD en EUR;
- automatische berekening van loon per periode in SRD;
- invoer van aantal kinderen voor de AKB-vrijstelling;
- invoer van vaste toelagen en inhoudingen via `sr_vaste_regels`;
- snelle contractinvoer voor standaardcomponenten zoals kinderbijslag, transport, representatie en geneeskundige behandeling.

Bij deze uitbreiding is niet alleen extra data toegevoegd, maar ook logica om de gegevens direct bruikbaar te maken voor payroll. Zo wordt voor FN-contracten het basisloon automatisch omgerekend van maandniveau naar het bedrag per fortnight. Ook is een live contractpreview gemaakt waarin bruto loon, belastbaar jaarloon, loonbelasting, AOV, geschat nettoloon en een eventuele FN26-jaarafronding zichtbaar worden.

Een belangrijk technisch detail is dat deze preview gebruikmaakt van dezelfde centrale berekeningslogica als de loonstrookverwerking. Daarmee is voorkomen dat gebruikers in het contractscherm een andere uitkomst zouden zien dan later op de loonstrook.

### 4.2 Realisatie van fiscale rekenlogica

De fiscale verwerking is gerealiseerd op basis van de Surinaamse loonbelastingregels en ondergebracht in salarisregels, parameters en centrale Python-logica. Hierbij is onder andere rekening gehouden met:

- periodieke loonbelasting volgens Artikel 14;
- AOV-bijdragen op periodiek loon;
- bijzondere beloningen volgens Artikel 17;
- uitkering ineens volgens Artikel 17a;
- overwerkbelasting volgens Artikel 17c;
- vrijgestelde en belastbare verwerking van kinderbijslag;
- aftrekbare posten zoals pensioen en andere belastingvrije aftrekken.

Binnen de salarisstructuur zijn hiervoor aparte regelcodes gebruikt, zoals `SR_LB`, `SR_AOV`, `SR_LB_BIJZ`, `SR_AOV_BIJZ`, `SR_LB_17A`, `SR_AOV_17A`, `SR_LB_OVERWERK` en `SR_AOV_OVERWERK`. Deze opbouw maakt de loonstrook technisch transparant en ondersteunt ook latere rapportage op artikelniveau.

Verder is multi-currency verwerking gerealiseerd. Het contractloon kan in vreemde valuta worden ingevoerd, waarna de actuele bedrijfskoers wordt gebruikt voor preview en omzetting naar SRD. Op de definitieve loonstrook wordt de gebruikte koers bevroren opgeslagen, zodat rapportages en controles achteraf reproduceerbaar blijven.

### 4.3 Configuratie en beheer

Voor beheerders en payrollgebruikers zijn aparte configuratieschermen gerealiseerd binnen `Payroll -> Configuratie -> Suriname`. Daaronder vallen onder andere:

- vaste looncodes;
- eenmalige looncodes;
- technische referentieparameters;
- SR Payroll Instellingen.

De schermen zijn zodanig ingericht dat gebruikers niet door alle algemene Odoo-parameters hoeven te navigeren. De Suriname-specifieke parameters zijn gefilterd en voorzien van duidelijke uitleg. Zo zijn er zoekfilters per onderwerp, zoals loonbelasting, AOV, overwerk, uitkering ineens en kinderbijslag. Hierdoor kunnen gebruikers sneller de juiste instellingen vinden en aanpassen.

### 4.4 Rapportage, wizardlogica en exports

Naast de payrollverwerking zelf zijn meerdere rapportageonderdelen gerealiseerd. Voorbeelden hiervan zijn:

- een Suriname-specifieke loonstrookrapportage;
- een fiscaal belastingoverzicht;
- een jaaropgavewizard per werknemer;
- bedrijfs- en periodeoverzichten;
- exporteerbare PDF-rapporten.

De jaaropgavewizard verzamelt loonstroken van een werknemer over een geselecteerd jaar, groepeert inkomenscomponenten, telt fiscale inhoudingen op en bouwt daarna een rapport op voor export. Daarmee is niet alleen een technisch werkend rapport gerealiseerd, maar ook een functioneel hulpmiddel voor HR en administratie.

Voor het fiscaal overzicht is een aparte PostgreSQL SQL-view gerealiseerd in het model `hr.payroll.tax.report`. Deze view verzamelt data uit bevestigde en betaalde loonstroken en groepeert bedragen zoals bruto loon, netto loon, ingehouden loonbelasting, AOV, kinderbijslag en uitsplitsingen per fiscaal artikel. De view is bewust alleen-lezen gemaakt, zodat gebruikers rapportagedata niet rechtstreeks kunnen wijzigen en altijd terug moeten naar de onderliggende loonstrook als correctie nodig is.

## 5. Samenvoegen van bestaande en nieuwe onderdelen

Een belangrijk onderdeel van de opdracht was het samenvoegen van bestaande applicatieonderdelen met nieuw ontwikkelde functionaliteit. Binnen dit project is daar bewust terughoudend en gestructureerd mee omgegaan.

Er is niet gekozen om payrollfunctionaliteit volledig opnieuw te bouwen. In plaats daarvan zijn bestaande Odoo-modellen en processen uitgebreid. Het standaard contractmodel bleef de basis voor de arbeidsrelatie, het standaard loonstrookmodel bleef de basis voor salarisverwerking en het standaard rapportmechanisme van Odoo bleef de basis voor PDF-uitvoer. De Suriname-specifieke logica is daarom toegevoegd als aanvulling op bestaande onderdelen en niet als concurrerende structuur ernaast.

Concreet betekent dit bijvoorbeeld dat:

- contracten zijn uitgebreid in plaats van vervangen;
- bestaande payroll salary rules zijn aangevuld met Suriname-specifieke regels;
- standaard `hr.rule.parameter` records zijn hergebruikt voor technische fiscale parameters;
- standaard Odoo views via inheritance zijn aangepast in plaats van volledig herschreven;
- transient wizards zijn gebruikt voor exportprocessen in plaats van losse maatwerkschermen.

Deze keuze heeft het project technisch sterker gemaakt. De oplossing blijft beter compatibel met Odoo, is begrijpelijker voor andere ontwikkelaars en sluit beter aan op toekomstig onderhoud of updates.

## 6. Ergonomisch verantwoorde interfaces

Bij de realisatie is expliciet rekening gehouden met ergonomie en gebruiksvriendelijkheid. Binnen een ERP-omgeving zoals Odoo betekent dat vooral dat schermen duidelijk moeten zijn, foutgevoelige invoer zo veel mogelijk wordt beperkt en dat gebruikers de juiste informatie op het juiste moment te zien krijgen.

Binnen dit project is dat op meerdere manieren gerealiseerd.

De contractinterface is opgesplitst in duidelijke delen zoals `Fiscale Data` en `Controle & Voorbeeld`. Hierdoor wordt eerst de invoer van gegevens gescheiden van de controle op de uitkomst. Dat verlaagt de kans op fouten en maakt het scherm beter leesbaar.

Daarnaast zijn contextuele waarschuwingen toegevoegd. Bij een negatief loonbedrag wordt direct een waarschuwing of validatiefout gegeven. Bij gebruik van een vreemde valuta krijgt de gebruiker een melding dat het loon tegen de actuele bedrijfskoers naar SRD wordt omgerekend. Ook is het aantal kinderen voor AKB begrensd en wordt de gebruiker daarop gewezen als de invoer buiten de toegestane grens valt.

Een ander ergonomisch aspect is het conditioneel tonen van velden. Velden voor loon per fortnight en FN26-correctie worden alleen zichtbaar wanneer een contract daadwerkelijk als FN is ingesteld. De actuele wisselkoers en SRD-omrekening worden alleen zichtbaar gemaakt als het contract niet in SRD staat. Dit voorkomt visuele ruis en maakt het formulier overzichtelijker.

Ook op configuratieniveau is ergonomie toegepast. In plaats van brede, technische lijsten zijn schermen ingericht met herkenbare titels, duidelijke categorieën, filters en uitgebreide helpteksten. Daardoor wordt de kans kleiner dat gebruikers verkeerde parameters aanpassen of een verkeerd type looncomponent selecteren.

Ten slotte is de rapportage ergonomisch verantwoord uitgewerkt door bedragen overzichtelijk te groeperen en onderscheid te maken tussen bruto, inhoudingen, netto en fiscale uitsplitsingen. De gebruiker hoeft daardoor niet zelf uit losse regels af te leiden wat de fiscale betekenis van een bedrag is.

## 7. Tussentijdse afstemming en bijsturing

Tijdens het realisatieproces zijn tussenresultaten besproken met de leidinggevende en waar nodig bijgestuurd. Die afstemming was belangrijk omdat dit project zowel juridische als technische aandachtspunten bevatte. Niet alleen moest de applicatie werken, maar de uitkomsten moesten ook begrijpelijk, reproduceerbaar en beheerbaar zijn.

Onderwerpen die om afstemming en bijsturing vroegen waren onder andere:

- de keuze om fiscale waarden configureerbaar te maken via parameters in plaats van vast in code te zetten;
- de keuze om contractpreview en loonstrooklogica op dezelfde berekeningsbasis te laten steunen;
- de manier waarop vreemde valuta en wisselkoersvastlegging in payroll moesten worden verwerkt;
- de inrichting van de fiscale rapportage als read-only SQL-view;
- de manier waarop gebruikers door configuratieschermen en wizards geleid worden.

Door deze punten tussentijds te bespreken kon de module stap voor stap worden aangescherpt. Dat is zichtbaar in keuzes zoals de centrale rekenopzet, de duidelijke scheiding tussen vaste en variabele looncomponenten, de extra waarschuwingen op contractniveau en de uitgebreide configuratiehulp voor beheerders.

## 8. Documentatie tijdens en na het realisatieproces

Tijdens en na de realisatie is structureel documentatie bijgehouden. Dit gebeurde niet alleen in een extern verslag, maar ook in en rondom de module zelf.

De documentatie binnen dit project bestaat onder andere uit:

- een README met functionele scope, releasenotes, installatie-informatie en test-VM instructies;
- het manifest met samenvatting, dependencies en een overzicht van alle geladen data, views, wizards en rapporten;
- helpteksten in configuratieschermen en formulieren;
- duidelijke benamingen van modelvelden, acties en rapporten;
- wizarddefinities en rapporttemplates die de werking van exports en PDF's structureren;
- ondersteunende scripts voor installatie, synchronisatie en beheer van de moduleomgeving.

Deze documentatie heeft meerdere doelen. Voor eindgebruikers en beheerders verduidelijkt zij hoe instellingen moeten worden gebruikt. Voor ontwikkelaars maakt zij zichtbaar hoe de module technisch is opgebouwd. Voor beoordelaars of projectbegeleiders laat zij zien dat niet alleen functionaliteit is gebouwd, maar dat er ook is nagedacht over overdraagbaarheid, onderhoud en beheer.

## 9. Koppeling aan het realisatieproces uit de opdracht

Onderstaand is zichtbaar hoe dit project aansluit op de gevraagde beroepshandeling.

- De applicatieontwikkelaar analyseert het functioneel en technisch ontwerp: dit is uitgevoerd door de bestaande Odoo payrollarchitectuur te onderzoeken en de Surinaamse fiscale eisen te vertalen naar modellen, salarisregels, parameters, rapporten en UI-keuzes.
- De applicatieontwikkelaar maakt zich programmeertaal en methodieken eigen: dit is zichtbaar in het gebruik van Python, XML, QWeb, Odoo ORM, inheritance, SQL-views en wizardmodellen.
- De applicatieontwikkelaar inventariseert interfaces: dit is gedaan door de koppelingen tussen contract, loonstrook, payrollinput, parameters, rapportage en multi-currency verwerking in kaart te brengen.
- De applicatieontwikkelaar realiseert onderdelen van een applicatie volgens opdracht: dit is terug te zien in contractuitbreidingen, fiscale rekenlogica, configuratieschermen, rapporten, wizards en exportfunctionaliteit.
- De applicatieontwikkelaar voegt onderdelen van bestaande applicaties samen: dit is gedaan door standaard Odoo-modellen en payrollprocessen uit te breiden in plaats van te vervangen.
- De applicatieontwikkelaar realiseert ergonomisch verantwoorde interfaces: dit blijkt uit de duidelijke contracttabbladen, helpteksten, waarschuwingen, filters, overzichtelijke wizardopbouw en conditionele zichtbaarheid van velden.
- De applicatieontwikkelaar bespreekt tussentijdse resultaten en past zo nodig aan: dit blijkt uit de gemaakte keuzes rond parametrisering, auditrapportage, centrale berekeningslogica en gebruikersgerichte schermopbouw.
- De applicatieontwikkelaar zorgt voor documentatie tijdens en na de realisatie: dit is gerealiseerd via README, manifest, schermhulp, rapportdefinities en ondersteunende scripts.

## 10. Resultaat en conclusie

Het realisatieproces heeft geleid tot een professioneel opgezet Odoo-project waarin juridische payrollregels, technische Odoo-uitbreiding, rapportage en gebruikersinterface samenkomen in een samenhangende oplossing. De module is niet alleen functioneel bruikbaar voor Surinaamse salarisverwerking, maar ook technisch onderhoudbaar doordat gebruik is gemaakt van bestaande Odoo-structuren, configureerbare parameters en gescheiden verantwoordelijkheden binnen de codebase.

De kracht van dit project ligt in de combinatie van analyse, technische uitwerking en praktische toepasbaarheid. Er is niet alleen een applicatieonderdeel gebouwd, maar ook een beheerbare en controleerbare payrolloplossing gerealiseerd. Daarmee sluit dit project inhoudelijk goed aan op de eisen van het realisatieproces: analyseren, interfaces inventariseren, ontwikkelen, integreren, ergonomisch uitwerken, afstemmen en documenteren.