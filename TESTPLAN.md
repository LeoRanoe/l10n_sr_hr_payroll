# Testplan — l10n_sr_hr_payroll (Surinaamse Salarismodule)
> **Odoo 18.0 Enterprise** · Database: `Salarisverwerking-Module` · April 2026  
> Wet Loonbelasting (WLB), S.B. 1981 No. 181, gewijzigd S.B. 2024 No. 2

---

## Referentieparameters 2026

Controleer vóór elke test of onderstaande waarden in het systeem staan.  
Pad: **Configuratie → Suriname → SR Belastingparameters**

| Code | Naam | Verwachte waarde |
|------|------|-----------------|
| `SR_BELASTINGVRIJ_JAAR` | Belastingvrije voet (Art. 14 lid 1) | SRD 108.000 / jaar |
| `SR_FORFAITAIRE_PCT` | Forfaitaire beroepskosten % (Art. 12) | 0,04 (= 4%) |
| `SR_FORFAITAIRE_MAX_JAAR` | Forfaitaire beroepskosten maximum (Art. 12) | SRD 4.800 / jaar |
| `SR_SCHIJF_1_GRENS` | Schijf 1 bovengrens (Art. 14) | SRD 42.000 / jaar |
| `SR_SCHIJF_2_GRENS` | Schijf 2 bovengrens (Art. 14) | SRD 84.000 / jaar |
| `SR_SCHIJF_3_GRENS` | Schijf 3 bovengrens (Art. 14) | SRD 126.000 / jaar |
| `SR_TARIEF_1` | Tarief schijf 1 (Art. 14) | 0,08 (= 8%) |
| `SR_TARIEF_2` | Tarief schijf 2 (Art. 14) | 0,18 (= 18%) |
| `SR_TARIEF_3` | Tarief schijf 3 (Art. 14) | 0,28 (= 28%) |
| `SR_TARIEF_4` | Tarief schijf 4 (Art. 14) | 0,38 (= 38%) |
| `SR_HEFFINGSKORTING_MAAND` | Heffingskorting (Art. 14 lid 5) | SRD 750 / maand |
| `SR_AOV_TARIEF` | AOV tarief (ALS 2005) | 0,04 (= 4%) |
| `SR_AOV_FRANCHISE_MAAND` | AOV franchise (ALS 2005) | SRD 400 / maand |
| `SR_BIJZ_VRIJSTELLING_MAX` | Max vrijstelling vakantie/gratificatie (Art. 10i/j) | SRD 10.016 / jaar |
| `SR_OWK_SCHIJF_1_GRENS` | Overwerk schijf 1 grens (Art. 17c) | SRD 2.500 / tijdvak |
| `SR_OWK_SCHIJF_2_GRENS` | Overwerk schijf 2 grens (Art. 17c) | SRD 7.500 / tijdvak |
| `SR_OWK_TARIEF_1` | Overwerk tarief 1 (Art. 17c) | 0,05 (= 5%) |
| `SR_OWK_TARIEF_2` | Overwerk tarief 2 (Art. 17c) | 0,15 (= 15%) |
| `SR_OWK_TARIEF_3` | Overwerk tarief 3 (Art. 17c) | 0,25 (= 25%) |

---

## FASE 1 — Gebruikers Aanmaken

### Stap 1.1 — HR Manager
1. Ga naar **Instellingen → Gebruikers → Nieuwe gebruiker aanmaken**
2. Vul in:
   - Naam: `HR Admin Test`
   - E-mail: `hr@test.sr`
   - Toegangsrechten → Werknemers: **Beheerder**
   - Toegangsrechten → Loonverwerking: **Beheerder**
3. Sla op. Noteer het wachtwoord of stel dit in via uitnodiging.

### Stap 1.2 — Payroll Manager
1. Maak een tweede gebruiker aan:
   - Naam: `Payroll Manager Test`
   - E-mail: `payroll@test.sr`
   - Toegangsrechten → Loonverwerking: **Beheerder**
2. Sla op.

**Verwacht resultaat:** Beide gebruikers zijn zichtbaar in Instellingen → Gebruikers.

---

## FASE 2 — Configuratie Controleren

### Stap 2.1 — Belastingparameters verifiëren
1. Ga naar **Configuratie → Suriname → SR Belastingparameters**
2. Controleer of alle 18 parameters uit de tabel hierboven aanwezig zijn met `date_from = 01/01/2026`

**Verwacht resultaat:** Alle 18 rijen zichtbaar, met correcte waarden.

### Stap 2.2 — Loon Code Types controleren
1. Ga naar **Configuratie → Suriname → Loon Code Types**
2. Controleer de aanwezigheid van onderstaande codes:

| Code | Categorie | Verwachte Effect |
|------|-----------|-----------------|
| OLIE | belastbaar | Verhoogt LB + AOV grondslag |
| KLEDING | belastbaar | Verhoogt LB + AOV grondslag |
| REPRESENTATIE | belastbaar | Verhoogt LB + AOV grondslag |
| TELEFOON | belastbaar | Verhoogt LB + AOV grondslag |
| KINDBIJ | vrijgesteld | Kinderbijslag — splitst in belastbaar/vrij |
| TRANSPORT | vrijgesteld | Geen LB of AOV |
| MAALTIJD | vrijgesteld | Geen LB of AOV |
| PENSIOEN | aftrek_belastingvrij | Verlaagt LB + AOV grondslag EN inhouding |
| ZIEKTEK | inhouding | Alleen netto-aftrek, geen LB/AOV effect |
| VAKBOND | inhouding | Alleen netto-aftrek |

### Stap 2.3 — SR Payslip Input Types controleren
1. Ga naar **Configuratie → Suriname → SR Payslip Input Types**
2. Controleer aanwezigheid van:

| Code | Categorie |
|------|-----------|
| SR_IN_BELASTB | belastbaar |
| SR_IN_VRIJ | vrijgesteld |
| SR_IN_GENEESKUNDE | belastbaar |
| SR_IN_AFTREK | inhouding |
| SR_IN_OVERWERK | overwerk |
| SR_IN_VAKANTIE | vakantie |
| SR_IN_GRAT | gratificatie |
| SR_IN_BIJZ_BEL | bijz_beloning |

### Stap 2.4 — Salarisstructuur verifiëren
1. Ga naar **Configuratie → Salaris → Salarisstructuren**
2. Open de structuur **"SR Loonstrook"**
3. Controleer of de volgende regels aanwezig zijn in volgorde:

| Seq | Code | Naam |
|-----|------|------|
| 10 | BASIC | Bruto Loon |
| 20 | SR_ALW | Belastbare Toelagen (Contract) |
| 21 | SR_KB_BELAST | Kinderbijslag Belastbaar Deel (Art. 10h) |
| 23 | SR_INPUT_BELASTB | Belastbare Toelagen (Payslip) |
| 30 | GROSS | Bruto Belastbaar Loon |
| 50 | SR_LB | Loonbelasting (Artikel 14 WLB) |
| 55 | SR_HK | Heffingskorting |
| 60 | SR_AOV | AOV Bijdrage |
| 65 | SR_AFTREK_BV | Aftrek Belastingvrij (Art. 10f) |
| 70 | SR_PENSIOEN | Vaste Inhoudingen (Contract) |
| 73 | SR_INPUT_AFTREK | Overige Inhoudingen (Payslip) |
| 80 | SR_KINDBIJ | Vaste Vrijgestelde Vergoedingen (Contract) |
| 81 | SR_KB_VRIJ | Kinderbijslag Vrijgesteld (Art. 10h) |
| 82 | SR_INPUT_VRIJ | Vrijgestelde Vergoedingen (Payslip) |
| 84 | SR_OVERWERK | Overwerk |
| 85 | SR_LB_OVERWERK | Loonbelasting Overwerk (Art. 17c) |
| 86 | SR_AOV_OVERWERK | AOV Overwerk |
| 87 | SR_VAKANTIE | Vakantietoelage |
| 88 | SR_GRAT | Gratificatie / Bonus |
| 89 | SR_BIJZ | Bijzondere Beloning |
| 91 | SR_LB_BIJZ | Loonbelasting Bijzondere Beloningen (Art. 17) |
| 92 | SR_AOV_BIJZ | AOV Bijzondere Beloningen |
| 100 | NET | Netto Loon |

---

## FASE 3 — Test Medewerkers en Contracten Aanmaken

Maak **5 verschillende test-medewerkers** aan. Dit zijn de medewerkers die we door alle scenario's heen gebruiken.

### Stap 3.1 — Medewerkers aanmaken
Ga naar **Medewerkers → Nieuw** voor elke medewerker:

| # | Naam | Afdeling | Functie | Opmerking |
|---|------|----------|---------|-----------|
| E1 | Test Medewerker — Basis | Administratie | Administratief Medewerker | Eenvoudig maandloon |
| E2 | Test Medewerker — Toelagen | Administratie | Senior Medewerker | Maandloon + belastbare toelage |
| E3 | Test Medewerker — Pensioen | Administratie | Manager | Maandloon + pensioen |
| E4 | Test Medewerker — Kinderen | Administratie | Medewerker | Maandloon + kinderbijslag |
| E5 | Test Medewerker — FN | Productie | Operator | Fortnight loon |

### Stap 3.2 — Contract E1: Basis Maandloon SRD 18.000
1. Open medewerker **E1** → tabblad **Contract** → klik **Nieuw Contract aanmaken**
2. Vul in:
   - Contractnaam: `Contract E1 - Basis`
   - Datum Start: `01/01/2026`
   - Salarisstructuur: **SR Loonstrook**
   - Surinaams Loontype: **Maandloon (12× per jaar)**
   - Maandloon: `18.000,00`
   - Aantal Kinderen: `0`
   - Vaste Loon Regels: *(leeg laten)*
3. Sla op en activeer het contract.

**Live Preview controle** (Tab "Surinaams Loon Preview" op contract):
- Bruto Loon: `18.000,00`
- Belastbaar Jaarloon: `103.200,00`
- LB per periode: `1.358,00`
- AOV per periode: `704,00`
- Geschat nettoloon: `16.688,00`

> Berekeningscontrole:  
> Bruto jaar = 18.000 × 12 = **216.000**  
> Forfaitair = min(216.000 × 4%, 4.800) = **4.800**  
> Belastbaar jaar = 216.000 − 108.000 − 4.800 = **103.200** ✓  
> LB schijf 1: 42.000 × 8% = 3.360  
> LB schijf 2: 42.000 × 18% = 7.560  
> LB schijf 3: 19.200 × 28% = 5.376  
> LB jaar totaal = **16.296** → per maand = **1.358,00** ✓  
> HK = min(9.000, 16.296) = **9.000** → per maand = **750,00**  
> AOV = (18.000 − 400) × 4% = **704,00** ✓  
> Netto = 18.000 − 1.358 + 750 − 704 = **16.688,00** ✓

### Stap 3.3 — Contract E2: Maandloon + Belastbare Toelagen
1. Maak contract aan voor **E2**:
   - Maandloon: `15.000,00`
   - Salarisstructuur: **SR Loonstrook**
   - Loontype: **Maandloon**
   - Vaste Loon Regels → voeg toe:
     - Type: **Olie Toelage**, Bedrag: `500,00` (vast bedrag)
     - Type: **Transportvergoeding**, Bedrag: `300,00` (vast bedrag)
2. Sla op.

**Live Preview controle:**
- Bruto Loon: `15.800,00` (= 15.000 + 500 belastbaar + 300 vrijgesteld)
- Belastbaar Jaarloon: `73.200,00`
- LB per periode: `748,00`
- AOV per periode: `604,00`
- Geschat nettoloon: `14.748,00`

> Berekeningscontrole:  
> GROSS = 15.000 + 500 = **15.500** (transport is vrijgesteld, telt niet mee)  
> Bruto jaar = 15.500 × 12 = **186.000**  
> Forfaitair = 4.800 (max)  
> Belastbaar jaar = 186.000 − 108.000 − 4.800 = **73.200** ✓  
> LB schijf 1: 42.000 × 8% = 3.360  
> LB schijf 2: (73.200 − 42.000) × 18% = 31.200 × 18% = 5.616  
> LB jaar = **8.976** → per maand = **748,00** ✓  
> HK = min(9.000, 8.976) = **8.976** → per maand = **748,00** (volledig gecrediteerd)  
> AOV = (15.500 − 400) × 4% = **604,00** ✓  
> Netto = 15.500 + 300 − 748 + 748 − 604 = **15.196,00**  
> *(De transportvergoeding SRD 300 telt mee in netto maar niet in LB/AOV)*

### Stap 3.4 — Contract E3: Maandloon + Pensioen (Aftrek Belastingvrij)
1. Maak contract aan voor **E3**:
   - Maandloon: `18.000,00`
   - Loontype: **Maandloon**
   - Vaste Loon Regels → voeg toe:
     - Type: **Pensioenpremie**, Bedragtype: **Percentage**, Percentage: `1,25%`, Basis: **Basisloon**
     - *(Dit berekent automatisch 1,25% × 18.000 = SRD 225/maand)*
2. Sla op.

**Live Preview controle:**
- LB per periode: `1.295,00` (lager dan E1 door pensioenaftrek!)
- AOV per periode: `695,00` (lager dan E1 door pensioenaftrek!)
- Geschat nettoloon: `16.535,00`

> Berekeningscontrole:  
> Pensioen = 1,25% × 18.000 = **225,00/maand**  
> Aftrek BV jaar = 225 × 12 = **2.700**  
> Adjusted bruto jaar = 216.000 − 2.700 = **213.300**  
> Forfaitair = 4.800  
> Belastbaar jaar = 213.300 − 108.000 − 4.800 = **100.500**  
> LB: S1=3.360, S2=7.560, S3=(100.500−84.000)×28%=4.620 → **15.540**  
> LB/maand = **1.295,00** ✓  
> HK = **750,00**  
> AOV grondslag = (18.000 − 225) − 400 = **17.375**  
> AOV = 17.375 × 4% = **695,00** ✓  
> Netto = 18.000 − 1.295 + 750 − 695 − 225 = **16.535,00** ✓  
> 💡 Let op: pensioen verlaagt ZOWEL de belastinggrondslag (minder LB+AOV) ALS het nettoloon.

### Stap 3.5 — Contract E4: Maandloon + Kinderbijslag + 3 Kinderen
1. Maak contract aan voor **E4**:
   - Maandloon: `15.000,00`
   - Loontype: **Maandloon**
   - Aantal Kinderen: `3`
   - Vaste Loon Regels → voeg toe:
     - Type: **Kinderbijslag**, Bedrag: `500,00`
2. Sla op.

**Live Preview controle:**
- Bruto Loon: `15.500,00` (= 15.000 + 375 vrij + 125 belastbaar)
- Belastbaar Jaarloon: `68.700,00`
- LB per periode: `680,50`
- AOV per periode: `589,00`

> Berekeningscontrole kinderbijslag splitsing (Art. 10h):  
> 3 kinderen × SRD 125/kind = SRD 375 → max SRD 500 → **vrijgesteld = 375**  
> Belastbaar KB = 500 − 375 = **125** → SR_KB_BELAST = 125  
> GROSS = 15.000 + 125 = **15.125**  
> Bruto jaar = 15.125 × 12 = **181.500**  
> Forfaitair = 4.800  
> Belastbaar jaar = 181.500 − 108.000 − 4.800 = **68.700** ✓  
> LB: S1=3.360 + S2=(68.700−42.000)×18%=4.806 → **8.166**  
> LB/maand = **680,50** ✓  
> HK = min(9.000, 8.166) = **8.166** → per maand = **680,50** (volledig gecrediteerd)  
> AOV = (15.125 − 400) × 4% = **589,00** ✓  
> Netto = 15.000 + 375 + 125 − 680,50 + 680,50 − 589 = **14.911,00**

### Stap 3.6 — Contract E5: Fortnight Loon
1. Maak contract aan voor **E5**:
   - Maandloon (per FN periode): `7.500,00`
   - Salarisstructuur: **SR Loonstrook**
   - Loontype: **Fortnight Loon (26× per jaar)**
   - Aantal Kinderen: `0`

**Live Preview controle:**
- Belastbaar Jaarloon: `73.200,00`

> Berekeningscontrole FN:  
> Bruto jaar = 7.500 × 26 = **195.000**  
> Forfaitair = 4.800 (max)  
> Belastbaar jaar = 195.000 − 108.000 − 4.800 = **82.200**  
> LB: S1=3.360 + S2=(82.200−42.000)×18%=7.236 → **10.596**  
> LB/FN = 10.596/26 = **407,54** (per fortnight periode)  
> HK/FN = min(9.000, 10.596)/26 = 9.000/26 = **346,15**  
> AOV: FN heeft **geen franchise** (alleen maandloon heeft SRD 400 franchise)  
> AOV = 7.500 × 4% = **300,00/FN** ✓  
> Netto/FN = 7.500 − 407,54 + 346,15 − 300 = **7.138,61**

---

## FASE 4 — Loonstroken Aanmaken en Berekeningen Verifiëren

### Stap 4.1 — Loonstroken batch genereren
1. Ga naar **Loonverwerking → Suriname → Loonstroken** of **Loonverwerking → Loonstroken**
2. Klik **Nieuw** of gebruik **Loonrun aanmaken**
3. Selecteer periode: **April 2026**
4. Selecteer structuur: **SR Loonstrook**
5. Voeg alle 5 test-medewerkers toe
6. Klik **Genereer loonstroken** of voeg ze één voor één aan

### Stap 4.2 — Loonstrook E1 controleren (Basis Maandloon)
1. Open de loonstrook van **E1** voor april 2026
2. Klik **Berekenen** (of "Bereken Loonstrook")
3. Open het tabblad **Loonregels** en controleer:

| Code | Naam | Verwacht bedrag |
|------|------|----------------|
| BASIC | Bruto Loon | + 18.000,00 |
| GROSS | Bruto Belastbaar | + 18.000,00 |
| SR_LB | Loonbelasting (Art. 14) | − 1.358,00 |
| SR_HK | Heffingskorting | + 750,00 |
| SR_AOV | AOV Bijdrage | − 704,00 |
| NET | Netto Loon | **16.688,00** |

> ⚠️ Controleer dat SR_ALW, SR_KB_BELAST niet verschijnen (werden niet ingesteld).  
> ⚠️ Controleer dat SR_HK als **positief creditbedrag** verschijnt.

### Stap 4.3 — Loonstrook E2 controleren (Belastbare toelagen + transport)
1. Open loonstrook **E2** → Bereken
2. Controleer loonregels:

| Code | Naam | Verwacht bedrag |
|------|------|----------------|
| BASIC | Bruto Loon | + 15.000,00 |
| SR_ALW | Belastbare Toelagen (olie) | + 500,00 |
| GROSS | Bruto Belastbaar | + 15.500,00 |
| SR_LB | Loonbelasting (Art. 14) | − 748,00 |
| SR_HK | Heffingskorting | + 748,00 |
| SR_AOV | AOV Bijdrage | − 604,00 |
| SR_KINDBIJ | Vrijgestelde vergoedingen (transport) | + 300,00 |
| NET | Netto Loon | **15.196,00** |

> 💡 De heffingskorting (748,00) is exact gelijk aan de bruto LB → netto LB = **0**  
> 💡 Transport (SR_KINDBIJ) verschijnt ná GROSS → raak LB/AOV niet aan  
> Netto check: 15.000 + 500 + 300 − 748 + 748 − 604 = **15.196,00** ✓

### Stap 4.4 — Loonstrook E3 controleren (Pensioen — Aftrek Belastingvrij)
1. Open loonstrook **E3** → Bereken
2. Controleer loonregels:

| Code | Naam | Verwacht bedrag |
|------|------|----------------|
| BASIC | Bruto Loon | + 18.000,00 |
| GROSS | Bruto Belastbaar | + 18.000,00 |
| SR_LB | Loonbelasting (Art. 14) | − 1.295,00 |
| SR_HK | Heffingskorting | + 750,00 |
| SR_AOV | AOV Bijdrage | − 695,00 |
| SR_AFTREK_BV | Aftrek Belastingvrij (pensioen) | − 225,00 |
| NET | Netto Loon | **16.535,00** |

> ⚠️ Vergelijk E3 met E1: zelfde basisloon SRD 18.000, maar door pensioen:  
> LB daalt van 1.358 naar **1.295** (SRD 63 minder belasting)  
> AOV daalt van 704 naar **695** (SRD 9 minder AOV)  
> SR_AFTREK_BV = −225 (dit is de feitelijke inhouding op nettolooon)

### Stap 4.5 — Loonstrook E4 controleren (Kinderbijslag splitsing)
1. Open loonstrook **E4** → Bereken
2. Controleer loonregels:

| Code | Naam | Verwacht bedrag |
|------|------|----------------|
| BASIC | Bruto Loon | + 15.000,00 |
| SR_KB_BELAST | KB Belastbaar (Art. 10h) | + 125,00 |
| GROSS | Bruto Belastbaar | + 15.125,00 |
| SR_LB | Loonbelasting (Art. 14) | − 680,50 |
| SR_HK | Heffingskorting | + 680,50 |
| SR_AOV | AOV Bijdrage | − 589,00 |
| SR_KB_VRIJ | KB Vrijgesteld (Art. 10h) | + 375,00 |
| NET | Netto Loon | **14.911,00** |

> 💡 KB van SRD 500 wordt gesplitst:  
> SRD 375 = vrijgesteld (3 kinderen × 125) → SR_KB_VRIJ  
> SRD 125 = belastbaar (boven de grens) → SR_KB_BELAST in GROSS  
> Netto check: 15.000 + 125 + 375 − 680,50 + 680,50 − 589 = **14.911,00** ✓

### Stap 4.6 — Loonstrook E5 controleren (Fortnight)
1. Open loonstrook **E5** voor een FN-periode (bijv. FN7: 26 maart – 8 april 2026)
2. Gebruik daarvoor de juiste datumrange voor een fortnight periode
3. Bereken en controleer:

| Code | Naam | Verwacht bedrag |
|------|------|----------------|
| BASIC | Bruto Loon | + 7.500,00 |
| GROSS | Bruto Belastbaar | + 7.500,00 |
| SR_LB | Loonbelasting (Art. 14) | − 407,54 |
| SR_HK | Heffingskorting | + 346,15 |
| SR_AOV | AOV Bijdrage | − 300,00 |
| NET | Netto Loon | **7.138,61** |

> ⚠️ Bij FN: AOV heeft **geen franchise** (de SRD 400 franchise geldt enkel voor maandloon).  
> Controleer: AOV = 7.500 × 4% = 300,00 (niet: (7.500 − 400) × 4%)

---7500

## FASE 5 — Bijzondere Beloningen Testen

### Stap 5.1 — Overwerk (Art. 17c)
Gebruik medewerker **E1** (of maak aparte loonstrook).

**Test A: Overwerk SRD 1.500 (in schijf 1)**
1. Open de loonstrook voor E1 → klik **Aanpassen**
2. Voeg Payslip Input toe:
   - Type: **Overwerk (Art. 17c)** (`SR_IN_OVERWERK`)
   - Bedrag: `1.500,00`
3. Bereken. Controleer:

| Code | Verwacht bedrag |
|------|----------------|
| SR_OVERWERK | + 1.500,00 |
| SR_LB_OVERWERK | − 75,00 |
| SR_AOV_OVERWERK | − 60,00 |

> Berekening overwerk LB (Art. 17c, schijf 1):  
> 1.500 ≤ 2.500 → 1.500 × 5% = **75,00** ✓  
> AOV overwerk: 1.500 × 4% = **60,00** (geen franchise) ✓

**Test B: Overwerk SRD 4.000 (over schijfgrens)**
1. Wijzig de overwerk input naar `4.000,00`
2. Bereken en controleer:

| Code | Verwacht bedrag |
|------|----------------|
| SR_OVERWERK | + 4.000,00 |
| SR_LB_OVERWERK | − 350,00 |
| SR_AOV_OVERWERK | − 160,00 |

> Berekening:  
> Schijf 1: 2.500 × 5% = 125,00  
> Schijf 2: (4.000 − 2.500) × 15% = 1.500 × 15% = 225,00  
> Totaal LB = 125 + 225 = **350,00** ✓  
> AOV: 4.000 × 4% = **160,00** ✓

> ⚠️ Let op: overwerk telt **niet** mee in GROSS (verschijnt ná seq 30).  
> De normale LB (SR_LB) verandert NIET als je overwerk toevoegt.

### Stap 5.2 — Vakantietoelage (Art. 10i) — Volledig Jaar
Gebruik medewerker **E1** (in dienst 01/01/2026).

1. Open een nieuwe loonstrook voor E1 (bijv. juni 2026)
2. Voeg Payslip Input toe:
   - Type: **Vakantietoelage (Art. 10i)** (`SR_IN_VAKANTIE`)
   - Bedrag: `20.000,00`
3. Bereken en controleer:

**Verwachte vrijstelling:** `min(18.000, 10.016)` = **10.016**  
**Belastbaar deel vacantie:** 20.000 − 10.016 = **9.984**

| Code | Verwacht bedrag |
|------|----------------|
| SR_VAKANTIE | + 20.000,00 |
| SR_LB | − 1.358,00 *(normaal, ongewijzigd)* |
| SR_HK | + 750,00 |
| SR_AOV | − 704,00 *(normaal, ongewijzigd)* |
| SR_LB_BIJZ | − 2.795,52 |
| SR_AOV_BIJZ | − 399,36 |

> Art. 17 marginaal tarief methode:  
> Belastbaar bijz = **9.984**  
> Gemiddelde/mnd = 9.984 / 12 = **832,00**  
> Gecorrigeerd loon/mnd = 18.000 + 832 = **18.832**  
> Gecorrigeerd belastbaar jaar = (18.832×12) − 108.000 − 4.800 = 225.984 − 112.800 = **113.184**  
> LB gecorrigeerd jaar: S1=3.360 + S2=7.560 + S3=(113.184−84.000)×28%=8.171,52 = **19.091,52**  
> HK gecorrigeerd = min(9.000, 19.091,52) = 9.000  
> Netto LB gecorr/mnd = (19.091,52 − 9.000)/12 = **840,96**  
> Netto LB normaal/mnd = (16.296 − 9.000)/12 = **608,00**  
> LB vakantie = (840,96 − 608,00) × 12 = **2.795,52** ✓  
> AOV vakantie = 9.984 × 4% = **399,36** ✓

**NET vakantietoelage loonstrook check:**  
18.000 + 20.000 − 1.358 + 750 − 704 − 2.795,52 − 399,36 = **33.493,12**

### Stap 5.3 — Gratificatie Pro-Rata (Art. 10j + Bug D fix)
Gebruik medewerker **E4** met datum in dienst **01/07/2026** (6 maanden in 2026).

> ⚠️ Pas het contract van E4 tijdelijk aan zodat datum in dienst = 01/07/2026

1. Maak loonstrook voor E4, **periode december 2026**
2. Voeg Payslip Input toe:
   - Type: **Gratificatie / Jaar Bonus (Art. 10j)** (`SR_IN_GRAT`)
   - Bedrag: `18.000,00`
3. Bereken.

**Verwachte vrijstelling pro-rata:**  
Maanden in dienst in 2026: juli t/m december = **6 maanden**  
Vrijstelling = min(15.000, 10.016) × 6/12 = 10.016 × 0,5 = **5.008,00**  
Belastbaar grat = 18.000 − 5.008 = **12.992,00**

Normaal LB/mnd (netto, na HK) voor GROSS = 15.000:
> Belastbaar jaar = 15.000×12 − 108.000 − 4.800 = 67.200  
> LB jaar = 3.360 + 4.536 = 7.896 → HK = 7.896 → Netto LB = 0/mnd

Art. 17 LB gratificatie:  
> Gemiddelde = 12.992/12 = **1.082,67**  
> Gecorrigeerd/mnd = 15.000 + 1.082,67 = **16.082,67**  
> Gecorrigeerd belastbaar jaar = 16.082,67×12 − 108.000 − 4.800 = **80.192,04**  
> LB gecorr: S1=3.360 + S2=(80.192−42000)×18%=6.874,56 = **10.234,56**  
> HK = min(9.000, 10.234,56) = 9.000  
> Netto LB gecorr/mnd = (10.234,56 − 9.000)/12 = **102,88**  
> Netto LB normaal = 0  
> **SR_LB_BIJZ = 102,88 × 12 = 1.234,56**

| Code | Verwacht bedrag |
|------|----------------|
| SR_GRAT | + 18.000,00 |
| SR_LB_BIJZ | − 1.234,56 |
| SR_AOV_BIJZ | − 519,68 *(= 12.992 × 4%)* |

> ⚠️ Als de datum in dienst **01/01/2026** zou zijn (heel jaar), dan:  
> Vrijstelling = 10.016 (100%) → belastbaar = 7.984 → LB lager  
> Dit is de **Bug D fix**: zonder pro-rata zou altijd de volle vrijstelling gelden.

---

## FASE 6 — Grensgeval Tests (Edge Cases)

### Stap 6.1 — Loon precies op belastingvrije grens (SRD 9.000/maand)
1. Maak tijdelijk een medewerker aan met maandloon **SRD 9.000**
2. Bereken loonstrook

**Verwacht:**
- SR_LB = **0,00** (belastbaar jaar = max(0, 108.000 − 108.000 − forfaitair) = 0)
- SR_HK = **0,00** (geen belasting dus geen heffingskorting)
- SR_AOV = − (9.000 − 400) × 4% = **− 344,00**
- NET = 9.000 − 344 = **8.656,00**

### Stap 6.2 — Hoog salaris in schijf 4 (boven SRD 126.000 belastbaar)
1. Maak tijdelijk medewerker aan met maandloon **SRD 25.000**
2. Bereken loonstrook

> Bruto jaar = 300.000  
> Belastbaar jaar = 300.000 − 108.000 − 4.800 = **187.200**  
> LB: S1=3.360 + S2=7.560 + S3=11.760 + S4=(187.200−126.000)×38%=23.256 = **45.936**  
> LB/mnd = **3.828,00**  
> HK = 750,00 (max)  
> AOV = (25.000 − 400) × 4% = **984,00**  
> Netto = 25.000 − 3.828 + 750 − 984 = **20.938,00**

### Stap 6.3 — Kinderbijslag met 4 kinderen (maksimum bereikt)
1. Contract instellen: 4 kinderen, KB = SRD 800/maand (d.i. > SRD 500 max)
2. Bereken loonstrook

**Verwacht KB splitsing:**
- 4 kinderen × 125 = 500 maar max is SRD 500/maand → **vrijgesteld = 500**
- Belastbaar deel = 800 − 500 = **300**
- SR_KB_BELAST = + 300
- SR_KB_VRIJ = + 500

### Stap 6.4 — Vakantietoelage kleiner dan de vrijstelling (volledig vrij)
1. Gebruik E1 (salaris SRD 18.000), vakantietoelage = **SRD 8.000**
2. Vrijstelling = min(18.000, 10.016) = **10.016**
3. Belastbaar = max(0, 8.000 − 10.016) = **0** → geen SR_LB_BIJZ, geen SR_AOV_BIJZ

**Verwacht:** SR_LB_BIJZ en SR_AOV_BIJZ verschijnen **niet** (bedrag = 0)

---

## FASE 7 — Loonstrook Bevestigen en Afdrukken

### Stap 7.1 — Loonstrook bevestigen
1. Open de berekende loonstrook van E1
2. Klik **Bevestigen** (status wordt: Bevestigd)
3. **Verwacht:** Status wijzigt van "Concept" naar "Bevestigd". Regels zijn niet meer aanpasbaar.

### Stap 7.2 — SR Loonstrook afdrukken (Surinaamse PDF)
1. Open de bevestigde loonstrook van E1
2. Zoek de knop **Loonstrook** of **Afdrukken** bovenaan
3. Klik op de knop om de Surinaamse loonstrook als PDF te openen

**Controleer op de PDF:**
- [ ] Medewerkersnaam correct
- [ ] Periode correct (maand + jaar)
- [ ] Bruto loon: `18.000,00`
- [ ] Loonbelasting: `1.358,00` (bruto, vóór heffingskorting)
- [ ] Heffingskorting: `750,00`
- [ ] AOV: `704,00`
- [ ] Nettoloon: `16.688,00`
- [ ] Tariefschijventabel (Art. 14) aanwezig met percentages
- [ ] Belastbaar jaarloon: `103.200,00`
- [ ] Forfaitaire aftrek: `4.800,00`

### Stap 7.3 — Loonstrook met bijzondere beloning afdrukken
1. Open de loonstrook van E1 met vakantietoelage SRD 20.000
2. Druk af

**Controleer op de PDF:**
- [ ] Vakantietoelage bruto: `20.000,00`
- [ ] Vrijstelling vakantie: `10.016,00`
- [ ] Belastbaar deel vakantie: `9.984,00`
- [ ] LB bijzondere beloning: `2.795,52`
- [ ] AOV bijzondere beloning: `399,36`
- [ ] Nettoloon totaal: `33.493,12`

### Stap 7.4 — Meerdere loonstroken tegelijk afdrukken
1. Ga naar **Loonverwerking → Loonstroken**
2. Selecteer (vinkje) meerdere bevestigde loonstroken
3. Klik **Afdrukken** of **Actie → Afdrukken**
4. **Verwacht:** Één PDF met alle geselecteerde loonstroken achter elkaar

---

## FASE 8 — Loonstroken Batch Aanmaken (Vrijwillig)

> **Opmerking:** De SR-module werkt met individuele loonstroken (hr.payslip), niet met een aparte Salarisrun-wrapper.
> Je kunt loonstroken één-voor-één aanmaken, of de standaard Odoo **Payroll Batches** gebruiken.

### Stap 8.1 — Loonstroken aanmaken voor april 2026 (Optie A: Individueel)
1. Ga naar **Loonverwerking → Loonstroken** (of **Payroll → All Payslips**)
2. Klik **+ Nieuw** voor elke medewerker:
   - Kies medewerker E1, E2, E3, E4
   - Selecteer periode: `01/04/2026 – 30/04/2026`
   - Selecteer structuur: **Suriname — Normaal Loon (Artikel 14 WLB)**
3. Sla op. Alle 4 loonstroken verschijnen in status "Concept"

**Verwacht:** 4 loonstroken aangemaakt in status "Concept"

### Stap 8.2 — Loonstroken berekenen (Batch)
1. Ga naar **Loonverwerking → Loonstroken** (of de SR snelkoppeling **Suriname → Loonstroken SR**)
2. Filter periode: `april 2026` of selecteer alle 4 loonstroken met vinkjes
3. Klik **Acties** → **Bereken** (of bereken ze één-voor-één met de knop in elk formulier)
4. **Verwacht:** Alle 4 loonstroken berekend, status = "Berekend"

### Stap 8.3 — Loonstroken bevestigen (Batch)
1. Ga naar de gefilterde loonstrokenlijst en selecteer alle 4 loonstroken
2. Klik **Acties** → **Bevestigen** (of bevestig ze één-voor-één)
3. **Verwacht:** Status = "Bevestigd" voor alle 4 loonstroken

> **Alternatief (Optie B: Payroll Batches):** Als je een formele salarisrun wilt bijhouden:
> 1. Ga naar **Payroll → Payroll Batches** (standaard Odoo functie, niet SR-specifiek)
> 2. Maak een batch aan en voeg loonstroken toe — maar dit is **optioneel**.

---

## FASE 9 — Suriname-sectie Navigatie Controleren

### Stap 9.1 — Snelkoppeling: Suriname → Loonstroken SR
1. Ga naar **Loonverwerking** (hoofd-menu)
2. Je ziet nu een sectie **Suriname** (toegevoegd door de SR-module)
3. Klik op **Suriname → Loonstroken SR (Art. 14)**

**Verwacht:**  
- Een gefilterd loonstrokenoverzicht alleen voor Surinaamse Art. 14 loonstroken
- Dezelfde loonstroken als via **Loonverwerking → Loonstroken**, maar vooraf gefilterd
- Dit is een **snelkoppeling** (geen aparte data, alleen filter)

### Stap 9.2 — Configuratie Suriname-menu
1. Ga naar **Configuratie → Suriname**
2. Je ziet de volgende opties (toegevoegd door de SR-module):
   - **SR Belastingparameters** — Art. 14 parameters (tarieven, grenzen, etc.)
   - **Loon Code Types** — Categorieën voor loonregels (belastbaar, vrijgesteld, aftrek, etc.)
   - **SR Payslip Input Types** — Payslip input types (overwerk, vakantie, gratificatie, etc.)

> 💡 Dit is een aparte **Configuratie → Suriname** sectie.
> Het standaard **Configuratie → Salaris** beheert Odoo payroll structuren en salary rules.

---

## FASE 10 — Extra Controles

### Stap 10.1 — Controle: Percentage-gebaseerde vaste loon regel
1. Ga naar contract van E3
2. Wijzig de pensioenpremie naar: **Bedragtype = Percentage, 2,5%, Basis = Basisloon**
3. Herbereken loonstrook E3

**Verwacht:**  
- Pensioen = 2,5% × 18.000 = **450,00/maand**
- SR_AFTREK_BV = −450,00
- LB lager dan bij 1,25% (aftrek is groter)

### Stap 10.2 — Controle: Belastbare toelage via Payslip Input
1. Maak nieuwe loonstrook voor E1 (zonder contract-toelagen)
2. Voeg toe via Payslip inputs:
   - Type: **Belastbare Toelage (Vrij te specificeren)** (`SR_IN_BELASTB`)
   - Bedrag: `1.000,00`
3. Bereken

**Verwacht:**
- SR_INPUT_BELASTB = + 1.000,00
- GROSS = 18.000 + 1.000 = **19.000**
- Hogere LB dan loonstrook zonder input

### Stap 10.3 — Controle: Vrijgestelde vergoeding via Payslip Input
1. Gebruik dezelfde loonstrook
2. Voeg toe via Payslip inputs:
   - Type: **Belastingvrije Vergoeding (Art. 10)** (`SR_IN_VRIJ`)  
   - Bedrag: `500,00`
3. Bereken

**Verwacht:**
- SR_INPUT_VRIJ = + 500,00
- GROSS ongewijzigd (500 vrij telt niet mee)
- LB ongewijzigd (alleen de belastbare 1.000 telt mee in grondslag)
- Netto stijgt wél met 500

---

## SAMENVATTING VERIFICATIETABEL

| Scenario | Salaris | Extra | LB/perioden | HK | AOV | Netto |
|----------|---------|-------|------------|-----|-----|-------|
| E1 Basis | 18.000 | — | 1.358,00 | 750,00 | 704,00 | 16.688,00 |
| E2 Toelage | 15.000 | +500 olie, +300 transport | 748,00 | 748,00 | 604,00 | 15.196,00 |
| E3 Pensioen | 18.000 | −225 pensioen | 1.295,00 | 750,00 | 695,00 | 16.535,00 |
| E4 Kinderen | 15.000 | +500 KB (3 kind.) | 680,50 | 680,50 | 589,00 | 14.911,00 |
| E5 FN | 7.500/FN | — | 407,54 | 346,15 | 300,00 | 7.138,61 |
| Edge: 9.000 | 9.000 | — | 0,00 | 0,00 | 344,00 | 8.656,00 |
| Edge: 25.000 | 25.000 | — | 3.828,00 | 750,00 | 984,00 | 20.938,00 |

---

## SCREENSHOTS CHECKLISTEN

Maak screenshots op de volgende momenten voor documentatie:

### Configuratie
- [ ] Screenshot: SR Belastingparameters overzicht (alle 18 rijen zichtbaar)
- [ ] Screenshot: Loon Code Types overzicht
- [ ] Screenshot: SR Payslip Input Types overzicht
- [ ] Screenshot: Salarisstructuur SR Loonstrook met alle regels

### Contracten
- [ ] Screenshot: Contract E1 tabblad "Surinaams Loon Preview" met berekeningsresultaten
- [ ] Screenshot: Contract E3 vaste loon regels (pensioenpremie met percentage)
- [ ] Screenshot: Contract E4 vaste loon regels (kinderbijslag + Aantal Kinderen = 3)
- [ ] Screenshot: Contract E3 tabblad "Tariefschijven" (HTML tabel met Art. 14 schijven)

### Loonstroken
- [ ] Screenshot: Loonstrook E1 tabblad Loonregels (alle regels met bedragen)
- [ ] Screenshot: Loonstrook E4 tabblad Loonregels (SR_KB_BELAST + SR_KB_VRIJ zichtbaar)
- [ ] Screenshot: Loonstrook E3 tabblad Loonregels (SR_AFTREK_BV zichtbaar)
- [ ] Screenshot: Loonstrook E1 + vakantietoelage (SR_LB_BIJZ + SR_AOV_BIJZ)
- [ ] Screenshot: Loonstrook E1 + overwerk (SR_LB_OVERWERK + SR_AOV_OVERWERK)

### Afdrukken
- [ ] Screenshot / PDF: SR Loonstrook E1 volledig afgedrukt
- [ ] Screenshot / PDF: SR Loonstrook met vakantietoelage en schijfberekening

---

## BEKENDE BEPERKINGEN

| Punt | Omschrijving |
|------|-------------|
| Vakantietoelage 1× vs 2× | Module berekent de belastinggrondslag correct. De **hoogte** van de vakantietoelage wordt handmatig ingevoerd via payslip inputs. |
| Multiple bijzondere beloningen | Als je zowel vakantie als gratificatie in dezelfde loonstrook invoert, worden beide **afzonderlijk** berekend. |
| FN franchise | AOV-franchise (SRD 400) wordt enkel toegepast bij maandloon. FN-lonerswerknemers betalen AOV over het volledig bruto bedrag per FN. |
| Datum in dienst = paramterdag | Als datum in dienst exact 1 januari is, is de pro-rata factor 12/12 = 1 (volledig jaar). |

---

*Gegenereerd: 13 april 2026 · l10n_sr_hr_payroll v18.0.2.0.0*
