# Suriname Payroll 2026 QA Audit

Dit document combineert UAT-stappen, auditnotities en go-live edge cases voor:

- Recht op Overwerk
- Dagelijkse Werkboekingen
- 2026 fiscale parameters
- CSV-import en interface-audit

## Voorbereiding

1. Update de module `l10n_sr_hr_payroll` naar de laatste build.
2. Gebruik een testdatabase met Suriname Payroll data geladen.
3. Maak drie testmedewerkers aan:
   - `UAT-MAAND-OT`
   - `UAT-FN-OT`
   - `UAT-MANAGER-GEEN-OT`
4. Controleer in Instellingen dat de 2026 parameters actief zijn:
   - `AKB per kind = 250`
   - `AKB maximum = 1000`
   - `Bijzondere beloning max = 19500`
   - `AOV franchise maand = 400`
   - `Overwerk factor 150 = 1.5`
   - `Overwerk factor 200 = 2.0`
5. Zet browser developer tools open zodat een refresh na save direct kan worden gecontroleerd.

## 1. Database Persistence UAT

### 1A. Werkboekingen blijven opgeslagen

1. Open Werkboekingen.
2. Maak een nieuwe boeking voor `UAT-MAAND-OT`.
3. Vul in:
   - datum/tijd op een maandag
   - duur `2,00`
   - overwerktype
   - bron `Import / Prikklok`
   - import batch `UAT-BATCH-001`
4. Sla op.
5. Refresh de browser volledig.
6. Open dezelfde boeking opnieuw.

Verwacht resultaat:

- De boeking bestaat nog.
- `Bron`, `Import Batch`, `OT 150% (u)` of `OT 200% (u)` blijven gevuld.
- Geen waarden springen terug naar leeg of `0,00` zonder gebruikersactie.

Afkeurcriterium:

- Waarden verdwijnen na refresh of heropenen.

### 1B. `Recht op Overwerk` op contract blijft bewaard

1. Open het contract van `UAT-MANAGER-GEEN-OT`.
2. Zet `Heeft Overwerkrecht` uit.
3. Sla op.
4. Sluit het formulier.
5. Open hetzelfde contract opnieuw.

Verwacht resultaat:

- `Heeft Overwerkrecht` blijft uitgevinkt.
- Het readonly uurloon blijft zichtbaar en consistent met het loon type.

Afkeurcriterium:

- Checkbox springt terug naar de vorige staat.

### 1C. Settings blijven permanent in `ir.config_parameter`

1. Open Payroll Instellingen.
2. Zet tijdelijk:
   - `AKB per kind = 250`
   - `Overwerk factor 150 = 1.75`
3. Sla op.
4. Sluit Instellingen.
5. Open Instellingen opnieuw.

Verwacht resultaat:

- Beide waarden blijven staan.
- Nieuwe loonstroken gebruiken direct de bijgewerkte factoren.

Afkeurcriterium:

- Instellingen vallen terug op oude waarden zonder bewuste rollback.

## 2. Werkboekingen naar Overwerk UAT

### Scenario A. Maandloper met recht op overwerk

Doel: 10 gewerkte uren op maandag eindigen als `8 uur normaal + 2 uur overwerk 150%`.

Teststappen:

1. Gebruik medewerker `UAT-MAAND-OT` met `Heeft Overwerkrecht = True`.
2. Registreer voor dezelfde maandag:
   - één normale boeking van `8,00` uur
   - één overwerkboeking van `2,00` uur
3. Valideer beide boekingen.
4. Maak een loonstrook voor die maand.

Verwacht resultaat:

- Normale boeking heeft `OT 150% = 0,00` en `OT 200% = 0,00`.
- Overwerkboeking heeft `OT 150% = 2,00`.
- De loonstrook krijgt input `Overwerk 150%`.

Audit-opmerking:

- Deze addon splitst nu niet zelfstandig één enkele `10,00`-uurs normale regel naar `8 + 2`.
- Als een CSV- of UI-flow later één regel van `10,00` uur aanbiedt, dan moet de eindstaat alsnog `8 normaal + 2 overwerk` worden. Blijft het één gewone 10-uursregel, dan is dat een defect of een ontbrekende feature.

### Scenario B. Fortnight medewerker met recht op overwerk

Doel: zondaguren worden automatisch `200% overwerk`.

Teststappen:

1. Gebruik medewerker `UAT-FN-OT` met loon type `FN` en `Heeft Overwerkrecht = True`.
2. Registreer een overwerkboeking op zondag.
3. Valideer de boeking.
4. Maak de fortnight loonstrook voor het juiste 2026 tijdvak.

Verwacht resultaat:

- Werkboeking toont `OT 200%` gelijk aan de geboekte uren.
- Loonstrook bevat input `Overwerk 200%`.
- AOV franchise wordt niet toegepast op FN.

### Scenario C. Geen recht op overwerk

Doel: extra uren wel registreren, maar niet als belastbaar overwerk uitbetalen.

Teststappen:

1. Gebruik medewerker `UAT-MANAGER-GEEN-OT` met `Heeft Overwerkrecht = False`.
2. Registreer een overwerkboeking van `4,00` uur.
3. Valideer de boeking.
4. Maak een loonstrook voor dezelfde periode.

Verwacht resultaat:

- Werkboeking mag nog steeds OT-buckets tonen.
- Loonstrook krijgt geen `Overwerk 150%` of `Overwerk 200%` input.
- Bruto loon bevat alleen het contractloon en andere expliciete componenten.

## 3. Fiscale Stress-Test 2026

### 3A. AKB cap check

1. Maak een contract met kinderbijslagregel van `1250`.
2. Test UI-gedrag met `5` kinderen.
3. Maak daarna de geldige variant met `4` kinderen.
4. Maak een loonstrook.

Verwacht resultaat:

- UI/backend accepteert niet meer dan `4` kinderen in deze release.
- Vrijgesteld deel wordt maximaal `1000`.
- Belastbaar deel wordt `250`.
- Nooit `1250` volledig vrijgesteld.

### 3B. Gratificatie check op `19500`

1. Maak loonstrook A met een gratificatie van exact `19500`.
2. Maak loonstrook B met een gratificatie van `20000`.

Verwacht resultaat:

- Bij `19500` is het belastbare bijzondere bedrag `0`.
- Bij `20000` is alleen `500` belastbaar.

### 3C. AOV franchise maand versus fortnight

1. Maak een maandloon loonstrook met bruto `4000`.
2. Maak een FN loonstrook met bruto `4000` per periode.

Verwacht resultaat:

- Maandloon: AOV franchise `400`, grondslag `3600`.
- FN: AOV franchise `0`, grondslag `4000`.

## 4. CSV Import Audit

Huidige status van de addon:

- Er zijn auditvelden voor import (`Bron`, `Import Batch`).
- Er is nog geen dedicated CSV-importwizard in deze addon.

Aanpak:

1. Test import via de standaard Odoo importflow of het externe importmechanisme dat jullie gebruiken.
2. Gebruik één geldige rij en één ongeldige rij met een onbekende werknemer-ID.

Verwacht resultaat:

- De ongeldige rij wordt geweigerd met een duidelijke foutmelding.
- Er ontstaat geen orphan work entry zonder werknemer of contract.
- Een succesvolle import vult `Bron = Import / Prikklok` en indien beschikbaar `Import Batch`.

Go-live blocker:

- Als onbekende werknemer-ID's stilzwijgend worden overgeslagen of aan de verkeerde werknemer koppelen, dan mag de import niet live.

## 5. Interface Audit Contractpagina

1. Open een contract.
2. Voeg minimaal `12` vaste loonregels toe met een mix van belastbaar, vrijgesteld en inhouding.
3. Controleer de Suriname payroll tab en de nieuwe overwerksectie.
4. Bewerk waarden, sla op en open het contract opnieuw.

Controlepunten:

- Tab blijft leesbaar zonder overlappende velden.
- `Heeft Overwerkrecht` en `Uurloon` blijven zichtbaar.
- Lange lijsten met toelagen breken layout, scroll en save niet.
- Geen onverwachte vertraging of browserfouten.

## Edge Cases Voor Go-Live

- Eén enkele 10-uurs normale boeking wordt niet automatisch opgesplitst naar 8 + 2.
- Handmatige override op een werkboeking moet buckets intact laten bij latere edits.
- Feestdagclassificatie moet ook werken voor niet-zondag feestdagen.
- Overwerk op zondag zonder overwerkrecht mag niet op de loonstrook verschijnen.
- Wijzigen van `Overwerk factor 150/200` moet nieuwe loonstroken beïnvloeden maar geen historische slips herschrijven.
- Gratificatie en vakantietoelage mogen elkaars vrijstellingscap niet verbruiken.
- FN loonstroken buiten de 2026 periodekalender moeten geweigerd blijven.
- Contractwissel midden in een loonperiode mag geen gecombineerde loonstrook doorlaten.
- Kinderbijslag zonder geregistreerde kinderen moet volledig belastbaar blijven.
- Onbekende werknemer-ID in import mag nooit een halfgevulde work entry achterlaten.
- Veel vaste loonregels op één contract mogen de contracttab niet onbruikbaar maken.