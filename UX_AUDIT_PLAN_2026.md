# UX Audit & Werkplan 2026

Doel van dit document:

- beoordelen of de Suriname Payroll module begrijpelijk genoeg is voor dagelijkse gebruikers
- controleren of de kernflows functioneel werken
- prioriteren welke verbeteringen eerst nodig zijn

Prioriteit in deze audit:

1. Gebruiksvriendelijkheid
2. Begrijpelijkheid van Werkboekingen
3. Functionele betrouwbaarheid

## Korte conclusie

De module bevat al veel fiscale logica en technische controle, maar de gebruikerservaring is nog niet overal consistent.
De grootste bron van verwarring zit in de werkboeking-flow:

- er zijn meerdere invoerpunten voor variabele looncomponenten
- oude en nieuwe uitleg over overwerk lopen door elkaar
- gebruikers zien statussen en afkortingen zonder duidelijk beslismodel

Dat betekent:

- functioneel kan veel al werken
- maar de kans op gebruikersfouten blijft te hoog zolang de flow niet eenvoudiger en consistenter wordt uitgelegd

## Auditbevindingen

### Kritiek

1. Helptekst en schermgedrag waren inhoudelijk tegenstrijdig.
   De help-template zei nog dat overwerk handmatig via Other Inputs moest, terwijl contract- en werkboekinglogica inmiddels automatische overwerk-sync ondersteunen.

2. Werkboekingen zijn conceptueel niet duidelijk genoeg voor payrollgebruikers.
   Een gebruiker moet nu zelf begrijpen wanneer iets een normale Attendance is, wanneer iets een SR overwerktype moet zijn, en wanneer een correctie via Other Inputs hoort.

### Hoog

3. Werkboekingen tonen technische statussen zonder eenvoudige taaktaal.
   Begrippen zoals Concept, Bevestigd, Conflict, OT 150% en OT 200% zijn niet meteen zelfverklarend.

4. De module heeft hulp, maar die hulp zit te ver weg van de taak.
   De algemene help-pagina bestaat al, maar ontbreekt als compacte contextuitleg precies in de werkboeking-flow.

5. De gebruiker mist een beslisboom.
   Er is geen korte regel als:
   - normale uren = attendance
   - extra uren werkdag = SR overwerk
   - zondag/feestdag = SR overwerk 200%
   - eenmalige payrollcorrectie = Other Input

### Middel

6. Contract, werkboeking en loonstrook gebruiken verschillende taalniveaus.
   Sommige schermen spreken over Art. 17c en categorieën, andere over gewone operationele acties. Dat is correct voor auditors, maar zwaar voor dagelijkse mutaties.

7. De lijstweergave is nog steeds vooral technisch georiënteerd.
   Begin/Einde/Duur zijn nuttig, maar het scherm vertelt niet expliciet wat de gebruiker vervolgens moet doen om een conflict op te lossen.

## Wat al is verbeterd

1. Conflict-work entries zijn corrigeerbaar gemaakt voor gewone gebruikers.
2. De SR-overwerksectie in het werkboekingformulier is uit de kapotte smalle kolom gehaald.
3. Er staat nu een inline hulptrigger in het werkboekingformulier.
4. De helptekst is bijgewerkt zodat automatische overwerk-sync niet meer wordt tegengesproken.

## Auditplan

### Fase 1. Begrijpelijkheid audit

Doel:
kunnen payrollgebruikers zonder uitleg snappen wat zij in Werkboekingen moeten doen?

Testgroep:

- 1 payrollgebruiker
- 1 contractbeheerder
- 1 functioneel beheerder

Taken:

1. Open Werkboekingen en leg in eigen woorden uit wat een conflictregel betekent.
2. Pas begin- en eindtijd van een conflictregel aan zonder hulp.
3. Leg uit wanneer je een werkboeking gebruikt en wanneer een Other Input.
4. Leg uit wat OT 150% en OT 200% betekenen.
5. Controleer of een contract met en zonder overwerkrecht logisch overkomt.

Succescriterium:

- minimaal 80% van de gebruikers kan deze taken zonder mondelinge hulp afronden

### Fase 2. Werkboeking-flow audit

Doel:
bevestigen dat de dagelijkse flow van contract naar werkboeking naar loonstrook logisch en zichtbaar is.

Testscenario's:

1. Maandwerknemer met overwerkrecht
   maak een normale attendance en een aparte SR overwerkregel op een werkdag

2. FN werknemer met overwerkrecht
   registreer zondagwerk en controleer 200%-classificatie

3. Werknemer zonder overwerkrecht
   registreer extra uren en controleer dat geen overwerkinput op de loonstrook verschijnt

4. Correctie op afgesloten periode
   bepaal of deze via werkboeking of Other Input moet lopen

Auditvragen:

- snapt de gebruiker waar de uren aangepast moeten worden?
- snapt de gebruiker waarom iets wel of niet op de loonstrook komt?
- is het verschil tussen registratie en uitbetaling duidelijk?

### Fase 3. Terminologie audit

Doel:
technische termen vervangen of aanvullen met taakgerichte taal.

Te toetsen termen:

- Werkboekingstype
- Conflict
- OT 150%
- OT 200%
- Handmatig Aangepast
- Other Inputs
- Bijzondere Beloning

Aanpak:

1. Per term laten uitleggen wat de gebruiker denkt dat het betekent.
2. Alles wat niet direct duidelijk is markeren voor hernoemen of tooltip.

### Fase 4. Functionele betrouwbaarheid

Doel:
controleren of de belangrijkste flows technisch kloppen nadat de UX duidelijker is gemaakt.

Te valideren:

1. Werkboekingen blijven opgeslagen na refresh.
2. Contractveld `Heeft Overwerkrecht` blijft persistent.
3. Config settings blijven in `ir.config_parameter` bewaard.
4. Overwerk 150% en 200% worden correct op de loonstrook gezet.
5. Geen overwerkrecht blokkeert variabele overwerkuitbetaling.
6. AKB, gratificatiegrens en AOV franchise volgen 2026-regels.

## Aanbevolen verbeterplan

### P0. Direct

1. Maak de werkboeking-flow op alle schermen inhoudelijk consistent.
2. Voeg een korte beslisboom toe in de werkboekingform en help-pagina.
3. Leg OT 150% en OT 200% uit in gewone taal.
4. Voeg een korte “Wanneer gebruik ik Werkboekingen / Other Inputs?” uitleg toe.

### P1. Binnen volgende iteratie

1. Voeg een compacte onboarding-card toe bovenin Werkboekingen.
2. Voeg tooltips of hernoemde labels toe voor Conflict, Overwerktype en Handmatig Aangepast.
3. Maak een korte stap-voor-stap taakhandleiding voor payrollmedewerkers.

### P2. Daarna

1. CSV-importflow expliciet ontwerpen en valideren.
2. Melding toevoegen als werknemer-ID of contract ontbreekt.
3. Eventueel wizard toevoegen die normale uren en overwerk visueel splitst.

## Go/No-Go voor livegang

Niet live zetten als één van deze punten nog onduidelijk of instabiel is:

1. Gebruikers weten niet wanneer zij Werkboekingen versus Other Inputs moeten gebruiken.
2. Overwerkrecht op contractniveau leidt tot verrassende loonstrookuitkomst.
3. Conflictregels zijn niet zonder beheerder oplosbaar.
4. Import of handmatige mutaties kunnen uren fout koppelen aan werknemer of periode.
5. De help-documentatie spreekt het schermgedrag nog tegen.

## Aanpak voor jouw reviewronde

Volg deze volgorde:

1. Begrijp eerst alleen Werkboekingen met 2 of 3 echte cases.
2. Controleer daarna pas de loonstrook-uitkomst.
3. Noteer per scherm waar je moest nadenken of twijfelen.
4. Alles wat niet binnen 5 seconden duidelijk is, behandelen als UX-issue.

## Verwachte uitkomst na de audit

Na deze audit moet je drie dingen kunnen zeggen:

1. Ik weet wat ik in Werkboekingen moet invullen.
2. Ik weet wanneer overwerk automatisch loopt en wanneer ik een Other Input gebruik.
3. Ik kan vertrouwen dat de loonstrook doet wat ik op het contract en in de werkboekingen heb ingevoerd.