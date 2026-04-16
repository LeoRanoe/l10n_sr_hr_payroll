# Audit Brief for Claude

## Executive Summary

Status: de module is niet veilig om als fiscaal-conforme 2026 implementatie te behandelen zolang de onderstaande fouten niet zijn gecorrigeerd.

Wat wel grotendeels goed zit:
- De basis-parameterisatie voor Art. 14 schijven (42.000 / 84.000 / 126.000 en 8% / 18% / 28% / 38%) is aanwezig.
- De forfaitaire aftrek van 4% met een jaarmaximum van SRD 4.800 is technisch ingebouwd.
- AOV voor normaal loon gebruikt 4%, met franchise voor maandloon en geen franchise voor FN.
- Overwerk gebruikt de 2026-contextschijven van 5% / 15% / 25% op 2.500 / 7.500.

Wat materieel fout is:
- De module past een aparte heffingskorting toe die niet door de formules en het worked example in `Loonbelasting context.md` wordt gedragen.
- De engine voor bijzondere beloningen wijkt op meerdere punten af van de broncontext: foutieve periodemultiplicatie, foutieve AOV-logica, foutieve vakantievrijstelling, geen jaarcap-handhaving en geen Art. 17a-pad.
- Kinderbijslag heeft een foutieve fallback wanneer het aantal kinderen ontbreekt.
- De contractpreview en het QWeb-rapport kunnen andere bedragen tonen dan de feitelijke salarisregels.
- De tests borgen een deel van de verkeerde logica en laten de risicovolste paden ongetest.

Conclusie: de module lijkt visueel compleet, maar de fiscale uitkomst is vooral onbetrouwbaar voor heffingskorting, bijzondere beloningen, kinderbijslag-edge-cases en audit-/rapportagesporen.

## Context for Claude

Gebruik `Loonbelasting context.md` als absolute bron van waarheid, ook als comments, tests of UI-teksten iets anders suggereren.

1. Normaal loon (Art. 14) wordt berekend door het belastbaar loon te annualiseren, de forfaitaire aftrek toe te passen, de belastingvrije som van SRD 108.000 af te trekken, daarna de schijven 8% / 18% / 28% / 38% toe te passen, en vervolgens terug te delen naar 12 of 26 periodes.
2. De worked example in de context levert voor het voorbeeldgeval `LB per maand = 2.634,71`. Die berekening trekt geen `SRD 750 * 12` af van de jaarbelasting. Behandel dus de formules en voorbeeldcijfers als leidend.
3. AOV is 4% over het belastbaar loon. Voor maandloon geldt een franchise van SRD 400 per maand. Voor FN geldt geen franchise.
4. Overwerk wordt apart belast via 5% / 15% / 25% op SRD 2.500 / 7.500 / rest, plus 4% AOV zonder franchise.
5. Bijzondere beloningen worden via de marginale methode berekend: belastbaar deel omzetten naar gemiddelde per tijdvak, optellen bij het normale belastbaar loon, LB/AOV herberekenen, en alleen het verschil per tijdvak inhouden. De `12` of `26` periodes zijn informatief en geen extra vermenigvuldigingsfactor.
6. Vakantietoelage heeft volgens de context een belastingvrij deel tot maximaal `2 x basisloon`, met een cap van SRD 10.016 per jaar.
7. Gratificatie heeft een vrijstelling die naar rato werkt; jaarmaxima zijn werkelijk jaarmaxima en mogen niet per payslip opnieuw volledig worden gebruikt.
8. Uitkering ineens / jubileum valt onder Art. 17a met eigen schijven `5% / 15% / 25% / 35% / 45%`, zonder belastingvrije som, en AOV = 4% van het lump-sum bedrag.
9. Kinderbijslag is alleen vrijgesteld tot `SRD 125 per kind per maand`, met een totaalmaximum van `SRD 500 per maand`.

## Gevonden Issues

### Issue 1 - Heffingskorting is ingebouwd als actieve belastingkorting, maar de bronformules doen dat niet

Severity: Critical

Locatie:
- `models/sr_artikel14_calculator.py:121-134`
- `reports/report_payslip_sr.xml:232-237`
- `reports/report_payslip_sr.xml:302-303`
- `tests/test_article_14.py:136`
- `tests/test_article_14.py:339`
- `tests/test_article_14.py:371`
- `tests/test_article_14_integration.py:126-131`

Omschrijving:
- `calculate_lb()` berekent eerst `lb_voor_heffingskorting`, zet daarna `heffingskorting_jaar = params['hk_maand'] * 12`, begrenst die korting op de bruto LB, en trekt die vervolgens af van de jaarbelasting.
- De loonstrookregels en rapportage modelleren dit als een aparte positieve regel `SR_HK`, bovenop een bruto `SR_LB`.

Waarom dit fout is volgens de broncontext:
- De formules in `Loonbelasting context.md` voor `LB_per_maand` en `LB_per_FN` trekken geen heffingskorting af.
- Het volledige worked example rekent `lb_jaar = 31.616,55` en `lb_per_maand = 2.634,71`, dus zonder vermindering met `SRD 750` per maand.
- De huidige code maakt van dezelfde jaarbelasting effectief `31.616,55 - 9.000 = 22.616,55`, oftewel `1.884,71` per maand. Dat wijkt materieel af van het voorbeeld dat de gebruiker als absolute waarheid heeft aangewezen.

### Issue 2 - LB op bijzondere beloningen wordt ten onrechte met 12 of 26 vermenigvuldigd

Severity: Critical

Locatie:
- `data/hr_salary_rule_data.xml:700-702`

Omschrijving:
- In `SR_LB_BIJZ` wordt eerst het verschil per tijdvak berekend via `lb_gecorr - lb_normaal`, maar daarna volgt `lb_bijz = max(0.0, lb_gecorr - lb_normaal) * periodes`.

Waarom dit fout is volgens de broncontext:
- De context zegt expliciet: de inhouding op een bijzondere beloning is het verschil per tijdvak, en `12` of `26` is informatief, niet een multiplier.
- De huidige code kan de inhouding dus met factor 12 of 26 overdrijven.

### Issue 3 - Meerdere bijzondere beloningen worden niet als een gecombineerde bijzondere beloning belast

Severity: High

Locatie:
- `data/hr_salary_rule_data.xml:669`
- `data/hr_salary_rule_data.xml:672`
- `data/hr_salary_rule_data.xml:700`
- `data/hr_salary_rule_data.xml:703`

Omschrijving:
- `lb_normaal` wordt eenmalig op de basisgrondslag bepaald.
- Daarna wordt over elke inputregel gelust en telkens `gecorrigeerd = gross_per_tijdvak + gemiddelde` berekend vanaf dezelfde onveranderde basisgrondslag.
- Als er in dezelfde loonstrook bijvoorbeeld zowel vakantietoelage als gratificatie voorkomt, dan wordt de tweede input niet belast bovenop de eerste gecorrigeerde grondslag.

Waarom dit fout is volgens de broncontext:
- De context beschrijft een bijzondere beloning als een bedrag dat eerst naar een gemiddeld bedrag per tijdvak wordt omgerekend en dan bij het normale loon wordt opgeteld om een gecorrigeerd tarief te bepalen.
- De comment in de XML zegt zelf dat deze regel vakantie + gratificatie + bijzondere beloning combineert, maar de implementatie combineert ze niet werkelijk.
- Bij progressieve belasting leidt dit tot onderinhouding zodra meerdere bijzondere bedragen samen in een hogere schijf vallen.

### Issue 4 - AOV op bijzondere beloningen gebruikt het volledige belastbare bedrag in plaats van het per-tijdvakverschil

Severity: Critical

Locatie:
- `data/hr_salary_rule_data.xml:734-755`
- `data/hr_salary_rule_data.xml:755`

Omschrijving:
- `SR_AOV_BIJZ` telt `aov_totaal += belastbaar * aov_tarief` op.
- `belastbaar` is hier het volledige belastbare bedrag van de bijzondere beloning, niet het gemiddelde per tijdvak.

Waarom dit fout is volgens de broncontext:
- De contextfunctie berekent `aov_bijzondere_beloning` vanuit het verschil per tijdvak: `(gecorrigeerd_loon - belastbaar_loon_tijdvak) * 0.04`.
- Dat verschil is het gemiddeld per tijdvak verdeelde bedrag, niet de volledige bonus.
- Voor een belastbare bijzondere beloning van SRD 12.000 bij maandloon hoort de context dus `12.000 / 12 * 4% = 40` te geven; de huidige code rekent `12.000 * 4% = 480`.

### Issue 5 - Vrijstelling voor vakantietoelage gebruikt 1x maandloon in plaats van 2x basisloon

Severity: High

Locatie:
- `data/hr_salary_rule_data.xml:682`
- `data/hr_salary_rule_data.xml:744`
- `models/hr_payslip_input_type.py:31-32`

Omschrijving:
- Voor `vakantie` gebruikt de code `vrijstelling = min(wage_maand, vrijstelling_max)`.
- De helptekst voor payslip input types documenteert dezelfde aanname.

Waarom dit fout is volgens de broncontext:
- De context zegt uitdrukkelijk: vakantietoelage is belastingvrij tot maximaal `2 x basisloon`, met een cap van `SRD 10.016 per jaar`.
- De huidige code beperkt de vrijstelling tot slechts `1 x` maandloon.
- Voor een basisloon van SRD 6.000 en een vakantietoelage van SRD 10.000 laat de context volledige vrijstelling toe; de huidige code belast onterecht SRD 4.000.

### Issue 6 - Jaarmaximum voor vakantie/gratificatie wordt niet over het kalenderjaar bewaakt

Severity: High

Locatie:
- `data/hr_salary_rule_data.xml:653`
- `data/hr_salary_rule_data.xml:672-689`
- `data/hr_salary_rule_data.xml:730`
- `data/hr_salary_rule_data.xml:736-752`

Omschrijving:
- De vrijstelling voor `vakantie` en `gratificatie` wordt per inputregel opnieuw bepaald via een lokale `min(...)`-berekening.
- Er is geen lookup naar eerder verbruikte vrijstelling in eerdere loonstroken van hetzelfde kalenderjaar.

Waarom dit fout is volgens de broncontext:
- De context noemt SRD 10.016 expliciet als jaarmaximum.
- De huidige implementatie kan dat maximum meerdere keren per jaar gebruiken, zowel over meerdere payslips als over meerdere inputregels in dezelfde payslip.
- Twee gratificaties van SRD 8.000 in hetzelfde jaar kunnen nu samen SRD 16.000 vrijstelling krijgen, terwijl de jaarcap SRD 10.016 is.

### Issue 7 - Art. 17a (uitkering ineens / jubileum) ontbreekt volledig en wordt foutief naar Art. 17 gerouteerd

Severity: Critical

Locatie:
- `data/hr_payslip_input_type_data.xml:114-120`
- `data/hr_salary_rule_data.xml:612-755`
- `data/hr_rule_parameter_data.xml` (geen Art. 17a parameterblok aanwezig)

Omschrijving:
- De module biedt alleen `bijz_beloning` aan voor jubileum-uitkeringen, afkoopsommen en vergelijkbare bedragen.
- Die route gebruikt de Art. 17 marginale methode en niet een aparte Art. 17a-berekening.
- Er zijn geen Art. 17a schijven, parameters of salarisregels aanwezig.

Waarom dit fout is volgens de broncontext:
- De context definieert voor uitkering ineens een aparte Art. 17a-logica met schijven `5% / 15% / 25% / 35% / 45%`, zonder belastingvrije som, plus AOV = 4% van het lump-sum bedrag.
- De huidige module kan zulke uitkeringen daarom alleen met de verkeerde methode belasten.

### Issue 8 - Kinderbijslag wordt volledig vrijgesteld zodra het aantal kinderen ontbreekt of 0 is

Severity: High

Locatie:
- `models/hr_contract.py:222-223`
- `models/hr_contract.py:226`

Omschrijving:
- `_sr_kinderbijslag_split()` retourneert `{'belastbaar': 0.0, 'vrijgesteld': total_kb}` als `sr_aantal_kinderen` niet gezet is of 0 is.

Waarom dit fout is volgens de broncontext:
- De vrijstelling is per kind gemaximeerd (`SRD 125 per kind per maand`) met een totaalmaximum van `SRD 500 per maand`.
- Bij 0 geregistreerde kinderen hoort de vrijgestelde ruimte dus 0 te zijn, niet het volledige bedrag.
- De huidige fallback maakt een ontbrekende stamgegeveninvoer direct tot een te gunstige fiscale uitkomst.

### Issue 9 - Contractpreview hardcode't kinderbijslaggrenzen en kan afwijken van de echte loonstrook

Severity: Medium

Locatie:
- `models/hr_contract.py:130`

Omschrijving:
- De preview gebruikt `contract._sr_kinderbijslag_split(125.0, 500.0)` met harde literals.
- De werkelijke salarisregels gebruiken daarvoor configureerbare `hr.rule.parameter` waarden.

Waarom dit fout is volgens de modulelogica:
- Zodra de parameterwaarden via payroll-configuratie worden aangepast, berekent de contractpreview iets anders dan de feitelijke loonstrook.
- Dit is geen theoretisch probleem: de module presenteert die parameters expliciet als configureerbaar.

### Issue 10 - De payslip-breakdown en het QWeb-rapport zijn geen betrouwbare weergave van de feitelijke loonstrook

Severity: High

Locatie:
- `models/hr_payslip.py:128`
- `models/hr_payslip.py:135`
- `models/hr_payslip.py:137`
- `data/hr_salary_rule_data.xml:247`
- `data/hr_salary_rule_data.xml:277`
- `data/hr_salary_rule_data.xml:331`
- `data/hr_salary_rule_data.xml:385`
- `reports/report_payslip_sr.xml:53`

Omschrijving:
- `_get_sr_artikel14_breakdown()` leest `SR_KINDBIJ` in als `kinderbijslag`, terwijl `SR_KINDBIJ` in werkelijkheid de regel is voor algemene vaste vrijgestelde vergoedingen. Het vrijgestelde deel van echte kinderbijslag zit in `SR_KB_VRIJ`.
- De breakdown herberekent belasting met `gross = basic + toelagen` en roept daarna `calc.calculate_lb(gross, periodes, params)` aan, zonder `aftrek_bv` en zonder meegenomen belastbare kinderbijslag of belastbare payslip inputs.
- Het QWeb-rapport voedt zichzelf volledig vanuit deze verkorte breakdown-dict in plaats van vanuit de echte loonstrookregels.

Waarom dit fout is:
- Het rapport kan andere bruto-, belasting- en netto-bedragen tonen dan de feitelijk berekende loonstrook zodra er `SR_KB_BELAST`, `SR_KB_VRIJ`, `SR_INPUT_BELASTB`, `SR_INPUT_VRIJ`, `SR_AFTREK_BV`, overwerk of bijzondere beloningen aanwezig zijn.
- Dat maakt de rapportage onbetrouwbaar als audit trail of werkgeversdocument.

### Issue 11 - De tests borgen de verkeerde heffingskorting-logica en missen de risicovolste fiscale paden

Severity: Medium

Locatie:
- `tests/test_article_14.py:136`
- `tests/test_article_14.py:166`
- `tests/test_article_14.py:339`
- `tests/test_article_14.py:371`
- `tests/test_article_14_integration.py:126-131`
- `tests/test_article_14_integration.py:228-240`

Omschrijving:
- Tests rekenen netto expliciet als `gross + lb + aov + hk` en de pure helper trekt jaarlijks `750 * 12` van de belasting af.
- De test-suite bevat geen gerichte dekking voor `SR_LB_BIJZ`, `SR_AOV_BIJZ`, kalenderjaar-caps, Art. 17a, of de kinderbijslag edge-case met ontbrekend kinderaantal.
- De FN AOV-test bevat bovendien een comment die nog een pro-rata franchise suggereert, terwijl de assertion gelukkig al op “geen franchise” zit.

Waarom dit relevant is:
- Als Claude de productcode corrigeert, blijven de huidige tests op de verkeerde logica staan of laten ze juist de gevaarlijkste regressies ongemerkt door.

## Fix Instructions

### Fix for Issue 1

- Verwijder de heffingskorting uit de fiscale Art. 14 engine als `Loonbelasting context.md` leidend blijft.
- Concreet: haal `hk_maand`, `heffingskorting_applied`, `heffingskorting_per_periode`, `lb_jaar_netto` en de aparte `SR_HK` loonstrookregel uit de berekening van de wettelijke inhouding.
- Pas contractpreview, paysliprapport, helpteksten en tests aan zodat `LB_per_maand` en `LB_per_FN` exact de contextformules volgen.
- Als business toch een aparte heffingskorting wil behouden, moet eerst de broncontext worden aangepast; binnen deze opdracht mag de code niet boven de broncontext prevaleren.

### Fix for Issue 2

- In `SR_LB_BIJZ` mag de uitkomst van `lb_gecorr - lb_normaal` niet meer met `periodes` worden vermenigvuldigd.
- Bereken één inhoudingsbedrag per payslip als het verschil per tijdvak en rond pas op het einde af op 2 decimalen.

### Fix for Issue 3

- Bouw eerst per bijzondere categorie het belastbare deel op na vrijstelling.
- Combineer daarna alle belastbare bijzondere bedragen tot één `belastbaar_bijz_totaal` voor de loonstrook.
- Bepaal één `gemiddelde = belastbaar_bijz_totaal / periodes`, één `gecorrigeerd_loon`, en één marginale LB-delta.
- Gebruik niet langer een loop die elke inputregel tegen dezelfde ongewijzigde `lb_normaal` afzet.

### Fix for Issue 4

- Herbouw `SR_AOV_BIJZ` vanuit dezelfde gecombineerde bijzondere grondslag als Issue 3.
- Volg de context letterlijk: AOV op bijzondere beloning is het verschil per tijdvak, dus `((belastbaar_bijz_totaal / periodes) * 0.04)`.
- Vermenigvuldig het volledige belastbare bonusbedrag niet meer rechtstreeks met 4%.

### Fix for Issue 5

- Splits de vrijstellingslogica per categorie.
- Voor `vakantie`: gebruik `min(2 * wage_maand, vrijstelling_remaining_cap)`.
- Voor `gratificatie`: behoud een aparte gratificatie-logica conform de context, inclusief proratering, maar niet dezelfde formule als `vakantie`.
- Werk ook de helpteksten en XML-comments bij zodat documentatie en code dezelfde regels tonen.

### Fix for Issue 6

- Introduceer een jaar-tot-datum lookup per werknemer en kalenderjaar voor reeds gebruikte vrijstelling op `vakantie` en `gratificatie`.
- Bereken eerst de resterende jaarcap (`max(0, jaarcap - reeds_gebruikt)`), en pas pas daarna de vrijstelling op de huidige payslip toe.
- Zorg dat meerdere inputregels in dezelfde payslip dezelfde resterende cap delen in plaats van elk een volledige cap te krijgen.

### Fix for Issue 7

- Voeg een aparte inputcategorie toe voor `uitkering_ineens` of `jubileum`.
- Maak aparte parameters voor Art. 17a-grenzen en tarieven: 42.000 / 84.000 / 126.000 / 168.000 met 5% / 15% / 25% / 35% / 45%.
- Implementeer aparte salarisregels voor LB en AOV op Art. 17a-uitkeringen.
- Routeer jubileum- en lump-sum uitbetalingen niet langer via `bijz_beloning` (Art. 17).

### Fix for Issue 8

- Pas `_sr_kinderbijslag_split()` aan zodat `sr_aantal_kinderen <= 0` niet automatisch tot volledige vrijstelling leidt.
- Veilig gedrag is: `vrijgesteld = 0`, `belastbaar = total_kb`, tenzij je een harde validatiefout wilt geven wanneer KINDBIJ aanwezig is zonder kinderaantal.
- Voeg een expliciete constraint of warning toe op contractniveau om ontbrekende kinderaantallen te blokkeren wanneer kinderbijslagregels bestaan.

### Fix for Issue 9

- Gebruik in `_compute_sr_preview()` geen harde `125.0` en `500.0`, maar haal de actuele parameterwaarden op uit `hr.rule.parameter`.
- Laat preview en echte loonstrook exact dezelfde parameterbron delen.

### Fix for Issue 10

- Schrijf `_get_sr_artikel14_breakdown()` om zodat de breakdown niet handmatig wordt gereconstrueerd uit een onvolledige subset van regels.
- Gebruik ofwel de werkelijk berekende loonstrookregels (`line_ids` per code) of voer exact dezelfde inputs door als de salarisregels gebruiken: `GROSS`, `SR_AFTREK_BV`, `SR_KB_BELAST`, `SR_KB_VRIJ`, `SR_INPUT_BELASTB`, `SR_INPUT_VRIJ`, `SR_OVERWERK`, `SR_LB_BIJZ`, `SR_AOV_BIJZ`.
- Corrigeer de labelmapping: `SR_KINDBIJ` is geen kinderbijslag, maar algemene vaste vrijgestelde vergoedingen; echte kinderbijslag-vrijstelling komt uit `SR_KB_VRIJ`.
- Laat het QWeb-rapport de echte loonstrookregels tonen voor alle debet- en creditcomponenten, niet alleen een verkorte breakdown.

### Fix for Issue 11

- Herschrijf de Art. 14 tests zodat zij de getallen uit `Loonbelasting context.md` volgen in plaats van de huidige `SR_HK`-logica.
- Voeg gerichte tests toe voor:
  - exact worked example maandloon uit de context;
  - FN AOV zonder franchise;
  - vakantietoelage met `2 x basisloon` vrijstelling;
  - hergebruik van de SRD 10.016 jaarcap over meerdere payslips;
  - meerdere bijzondere inputregels in één payslip;
  - Art. 17a uitkering ineens;
  - kinderbijslag met `sr_aantal_kinderen = 0` of leeg;
  - consistentie tussen rapportage en echte loonstrookregels.
- Verwijder of corrigeer comments die nog een pro-rata FN-franchise suggereren.

## Implementation Priority

Aanbevolen volgorde voor Claude:

1. Corrigeer eerst de beslisregels voor heffingskorting, bijzondere beloningen en Art. 17a.
2. Corrigeer daarna kinderbijslag en jaarcap-logica.
3. Herbouw vervolgens preview- en rapportagepaden zodat die dezelfde engine gebruiken.
4. Werk ten slotte de tests bij en voeg ontbrekende dekking toe.

## Important Constraint

Probeer de huidige comments, UI-helpteksten en tests niet als waarheid te behandelen. Voor deze audit is `Loonbelasting context.md` het leidende document.