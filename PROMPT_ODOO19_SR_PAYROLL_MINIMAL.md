# Handover-prompt: Minimale Suriname Payroll voor Odoo 19 (`/home/shared`)

> **Hoe te gebruiken:** plak alles vanaf "### START PROMPT" in een nieuwe Claude Code /
> agent-sessie die **wél** SSH-toegang heeft tot `leonardo@51.81.85.133`.
> Het document is bewust self-contained: alle wettelijke parameters en formules
> staan erin, zodat de nieuwe sessie de oude repo niet nodig heeft.
>
> Bron van de parameters: de bestaande module `l10n_sr_hr_payroll`
> (Odoo 18, branch `claude/odoo-payroll-suriname-2026-1g4qwl`),
> bestanden `data/hr_rule_parameter_data.xml`, `data/hr_salary_rule_data.xml`,
> `models/sr_artikel14_calculator.py`, `tests/test_article_14.py`.

---

### START PROMPT

## 0. Rol en doel

Je bouwt een **minimale, wettelijk correcte Suriname-payroll voor Odoo 19** op de
ontwikkelserver, in de gedeelde ontwikkelmap `/home/shared`. Het eindresultaat moet
zijn: **een loonrun die je kunt draaien, bevestigen en uitbetalen**, met Surinaamse
loonbelasting (Wet Loonbelasting, tarieven 2026) en AOV correct ingehouden.

Leidend principe: **minimale customization**. Gebruik zoveel mogelijk standaard Odoo
payroll (`hr.payroll.structure`, `hr.salary.rule`, `hr.rule.parameter`) en voeg alleen
Python/velden toe waar de standaard het echt niet kan. Liever 300 regels die werken dan
8.000 regels die onderhouden moeten worden.

**Verboden:** een 1-op-1 port van de bestaande Odoo 18-module (8.400 regels models +
data, eigen wizards, eigen SQL-views, eigen rapporten, multi-currency FX-lock). Dat is
expliciet buiten scope. Neem alleen de **parameters en formules** over die hieronder
staan.

## 1. Omgeving

| Item | Waarde |
|---|---|
| SSH | `leonardo@51.81.85.133` |
| Odoo | versie 19 (draait in een container — verifieer hoe) |
| Werkmap | `/home/shared` (gedeelde dev-map) |
| Doelland | Suriname (`base.sr`), valuta SRD |
| Wetgeving | Wet Loonbelasting Suriname, tarieven **2026** |

## 2. Fase 0 — Verkenning vóór je één regel code schrijft

Voer dit uit en **rapporteer de uitkomsten terug** voordat je begint te bouwen.
Een aantal aannames hieronder kan de hele aanpak omgooien.

```bash
ssh leonardo@51.81.85.133
```

Onderzoek en noteer:

1. **Odoo-editie en -versie.**
   - `odoo-bin --version` of het versienummer in de container.
   - **Kritiek:** `hr_payroll` zit in Odoo **Enterprise**, niet in Community.
     Controleer of `hr_payroll` in het addons-pad aanwezig is:
     `find / -name "hr_payroll" -maxdepth 8 -type d 2>/dev/null`
   - Als `hr_payroll` **ontbreekt** → STOP en meld dit. Zonder `hr_payroll` bestaan
     `hr.payslip`, `hr.salary.rule` en `hr.rule.parameter` niet en is er geen
     payroll-engine om op te bouwen. Opties zijn dan: Enterprise-licentie, OCA
     `payroll` (ander datamodel, geen `hr.rule.parameter`), of een eigen engine —
     dat is een andere opdracht met een andere omvang.

2. **`hr.contract` of `hr.version`?**
   Vanaf Odoo 18.2/19 is het contractmodel samengevoegd in `hr.version` op de
   werknemer. Verifieer in de echte source van de container:
   ```bash
   grep -rn "_name = 'hr.contract'\|_name = 'hr.version'" <addons>/hr_contract <addons>/hr /dev/null
   grep -rn "version_id\|contract_id" <addons>/hr_payroll/models/hr_payslip.py | head
   ```
   Kijk óók welke variabelen de salarisregel-evaluatie (`localdict`) aanbiedt:
   ```bash
   grep -rn "localdict\|'contract'\|'version'\|'employee'" <addons>/hr_payroll/models/hr_payslip.py | head -40
   ```
   Dit bepaalt of je in `amount_python_compute` `contract.` of `version.` schrijft.
   **Ga hier niet vanuit — lees de code.**

3. **Container-, database- en deploybeheer.**
   - Hoe start/herstart je Odoo? (docker compose, systemd, ...)
   - Welke databases bestaan er? Welke is productie en welke mag je slopen?
   - Waar staat het custom addons-pad en staat `/home/shared` daar al in
     (`odoo.conf` → `addons_path`)? Zo niet: voeg het toe.
   - Maak een **verse testdatabase** aan. Werk nooit direct in productie.

4. **Aanwezige modules:** `hr`, `hr_contract`/`hr_version`, `hr_payroll`,
   `hr_payroll_account` (voor boekingen), `account`, `hr_work_entry*`.

5. **Valuta SRD:** bestaat `res.currency` SRD en is die actief? Is de bedrijfsvaluta SRD?

6. **Backup** van de doel-database vóór elke install/upgrade.

## 3. Scope

### In scope (fase 1 — dit moet werken)

- Salarisstructuur "Suriname — Normaal Loon (Art. 14 WLB)" voor **maandloon (12 periodes)**.
- Loonbelasting Artikel 14 (progressief, jaarbasis → periode).
- Forfaitaire beroepskostenaftrek Art. 12.
- Belastingvrije som Art. 13.
- AOV-inhouding.
- Kinderbijslag Art. 10h (vrijgesteld deel + belastbaar surplus).
- Belastbare toelagen en vrijgestelde vergoedingen.
- Aftrek belastingvrij Art. 10f (pensioenpremie: verlaagt de grondslag én netto).
- Loonstrook berekenen → bevestigen → **betalen** (zie §7).

### Fase 2 (pas na akkoord van de gebruiker, alleen als fase 1 groen is)

- Overwerk Art. 17c.
- Bijzondere beloningen Art. 17 (vakantietoelage, gratificatie).
- Uitkering ineens / jubileum Art. 17a.
- FN-loon (26 periodes).

### Expliciet buiten scope

Multi-currency/FX-lock, eigen PDF-loonstrookrapporten, verzamelloonstaat-wizards,
jaaropgave-wizards, eigen SQL-view rapportage, dashboards, help-pagina's,
werkkalender-/work-entry-maatwerk.

## 4. De wettelijke parameters 2026 (SRD)

Leg deze vast als `hr.rule.parameter` + `hr.rule.parameter.value` met
`date_from = 2026-01-01` en `country_id = base.sr`. Datum-gebaseerd, zodat een
wetswijziging alleen een nieuw `.value`-record met een nieuwe `date_from` kost.

### Art. 12 / 13 — aftrekken

| Code | Betekenis | Waarde 2026 |
|---|---|---|
| `SR_BELASTINGVRIJ_JAAR` | Belastingvrije som per jaar (Art. 13) | `108000.0` |
| `SR_FORFAITAIRE_PCT` | Forfaitaire beroepskosten % (Art. 12) | `0.04` |
| `SR_FORFAITAIRE_MAX_JAAR` | Maximum forfaitaire aftrek per jaar | `4800.0` |

### Art. 14 — progressieve schijven (belastbaar jaarloon)

| Code | Waarde | Schijf | Tarief |
|---|---|---|---|
| `SR_SCHIJF_1_GRENS` | `42000.0` | 0 – 42.000 | 8 % |
| `SR_SCHIJF_2_GRENS` | `84000.0` | 42.000 – 84.000 | 18 % |
| `SR_SCHIJF_3_GRENS` | `126000.0` | 84.000 – 126.000 | 28 % |
| — | — | > 126.000 | 38 % |

| Code | Waarde |
|---|---|
| `SR_TARIEF_1` | `0.08` |
| `SR_TARIEF_2` | `0.18` |
| `SR_TARIEF_3` | `0.28` |
| `SR_TARIEF_4` | `0.38` |

### AOV

| Code | Betekenis | Waarde 2026 |
|---|---|---|
| `SR_AOV_TARIEF` | AOV-tarief werknemer | `0.04` |

> Let op: in de 2026-berekening is er **géén** actieve AOV-franchise. De AOV-grondslag
> is het loon ná Art. 10f-aftrek en ná de Art. 12 forfaitaire aftrek. Zie §5.

### Art. 10h — kinderbijslag

| Code | Betekenis | Waarde 2026 |
|---|---|---|
| `SR_KINDBIJ_MAX_KIND_MAAND` | Vrijstelling per kind per maand | `250.0` |
| `SR_KINDBIJ_MAX_MAAND` | Vrijstelling totaal per maand | `1000.0` |

### Art. 9 — vrije geneeskundige behandeling (voordeel in natura)

| Code | Betekenis | Waarde 2026 |
|---|---|---|
| `SR_VGB_MAX_JAAR` | Fiscaal belastbaar maximum per jaar | `200.0` |

### Fase 2 — Art. 17c overwerk (per tijdvak)

| Code | Waarde | Schijf | Tarief |
|---|---|---|---|
| `SR_OWK_SCHIJF_1_GRENS` | `2500.0` | 0 – 2.500 | 5 % |
| `SR_OWK_SCHIJF_2_GRENS` | `7500.0` | 2.500 – 7.500 | 15 % |
| — | — | > 7.500 | 25 % |
| `SR_OWK_TARIEF_1` | `0.05` | | |
| `SR_OWK_TARIEF_2` | `0.15` | | |
| `SR_OWK_TARIEF_3` | `0.25` | | |

### Fase 2 — Art. 10i/10j + Art. 17a

| Code | Betekenis | Waarde 2026 |
|---|---|---|
| `SR_BIJZ_VRIJSTELLING_MAX` | Vrijstelling vakantietoelage + gratificatie per jaar | `19500.0` |
| `SR_17A_SCHIJF_1_GRENS` | Art. 17a schijf 1 | `42000.0` |
| `SR_17A_SCHIJF_2_GRENS` | Art. 17a schijf 2 | `84000.0` |
| `SR_17A_SCHIJF_3_GRENS` | Art. 17a schijf 3 | `126000.0` |
| `SR_17A_TARIEF_1..4` | Art. 17a tarieven | `0.05 / 0.15 / 0.25 / 0.35` |

### Vervallen / inactief in 2026

- **Heffingskorting** (`SR_HEFFINGSKORTING`): waarde `0.0`. Wordt in de 2026-formule
  **niet** toegepast; Art. 13 doet het werk via de belastingvrije som. Neem deze regel
  niet op in de nieuwe module.
- **AOV-franchise** (`SR_AOV_FRANCHISE_MAAND`): `0.0`, legacy. Niet overnemen.
- **Solidariteitsheffing 45 %**: vervallen. Niet overnemen.

> **Verificatieplicht vóór productie:** bovenstaande bedragen komen uit de bestaande
> Odoo 18-module en zijn dáár de 2026-implementatie. Ze zijn niet onafhankelijk
> geverifieerd tegen de gepubliceerde wettekst. Laat de gebruiker of de fiscalist
> de belastingvrije som, de schijfgrenzen en de tarieven bevestigen tegen de officiële
> bron (Belastingdienst Suriname / Staatsblad) voordat er echt uitbetaald wordt.

## 5. De berekening (dit is de kern — implementeer exact zo)

Alle geldberekeningen met `decimal.Decimal` en `ROUND_HALF_UP` op 2 decimalen, niet met
floats. Rond pas af op het eindresultaat per regel, niet tussentijds.

Gegeven: `bruto_per_periode` (= GROSS), `periodes` (12 bij maandloon),
`aftrek_bv_per_periode` (Art. 10f pensioenpremie).

```
# 1. Naar jaarbasis
bruto_jaar            = bruto_per_periode * periodes
aftrek_bv_jaar        = aftrek_bv_per_periode * periodes

# 2. Art. 10f — pensioenpremie verlaagt de grondslag
adjusted_bruto_jaar   = max(0, bruto_jaar - aftrek_bv_jaar)

# 3. Art. 12 — forfaitaire beroepskosten (4 %, max 4.800/jaar)
forfaitaire_jaar      = min(adjusted_bruto_jaar * 0.04, 4800)
forfaitaire_periode   = forfaitaire_jaar / periodes

# 4. Grondslag ná Art. 12
grondslag_jaar        = max(0, adjusted_bruto_jaar - forfaitaire_jaar)
grondslag_periode     = max(0, (bruto_per_periode - aftrek_bv_per_periode) - forfaitaire_periode)

# 5. Art. 13 — belastingvrije som
belastbaar_jaar       = max(0, grondslag_jaar - 108000)

# 6. Art. 14 — progressieve schijven over belastbaar_jaar
#    per schijf: basis = max(0, min(belastbaar_jaar, bovengrens) - ondergrens)
#                tax   = basis * tarief
lb_jaar               = som(tax over alle schijven)
lb_per_periode        = lb_jaar / periodes

# 7. AOV — 4 % over de grondslag ná Art. 10f én Art. 12, per periode
aov_per_periode       = grondslag_periode * 0.04
```

Belangrijke details die makkelijk fout gaan:

- De **AOV-grondslag is dezelfde grondslag als de LB-grondslag** (ná forfaitaire
  aftrek), niet het kale brutoloon. Bij maandloon en een hoog salaris komt de aftrek
  neer op SRD 400/maand (4.800 / 12), omdat het jaarmaximum bindend is.
- De belastingvrije som en het forfaitaire maximum zijn **jaarbedragen**. Reken altijd
  eerst naar jaarbasis, pas de aftrekken en de schijven op jaarbasis toe, en deel het
  resultaat pas daarna door het aantal periodes. Niet andersom.
- `lb_per_periode` moet exact `lb_jaar / periodes` zijn.
- Loonbelasting en AOV zijn inhoudingen: **negatieve** bedragen in de DED-categorie.

### Kinderbijslag (Art. 10h)

```
vrijstelling = min(aantal_kinderen * 250, 1000)      # per maand
vrijgesteld  = min(kinderbijslag_bedrag, vrijstelling)
belastbaar   = max(0, kinderbijslag_bedrag - vrijgesteld)
```
Het vrijgestelde deel telt **niet** mee in GROSS (geen LB/AOV) maar wél in netto.
Het belastbare surplus telt **wél** mee in GROSS.

### Fase 2 — Art. 17c overwerk

Eigen schijven over het bruto overwerkbedrag **per tijdvak** (niet naar jaarbasis,
geen belastingvrije som):
`≤ 2.500 → 5 %`; `≤ 7.500 → 2.500×5 % + rest×15 %`;
`> 7.500 → 2.500×5 % + 5.000×15 % + rest×25 %`. AOV = 4 % over het bruto overwerk.

### Fase 2 — Art. 17 bijzondere beloningen (marginaal tarief)

```
vrijstelling vakantietoelage = min(2 × basisloon, restant jaarcap 19.500)
vrijstelling gratificatie    = min(1 × basisloon, restant jaarcap 19.500)
belastbaar_bijz              = som(bijzondere beloningen) - vrijstellingen
gemiddelde                   = belastbaar_bijz / periodes
lb_bijz = (lb_periode(gross + gemiddelde) - lb_periode(gross)) * periodes
aov_bijz = belastbaar_bijz * 0.04
```
De jaarcap van 19.500 is **gedeeld** tussen vakantietoelage en gratificatie en vereist
een YTD-lookup over eerdere loonstroken van hetzelfde jaar.

## 6. Voorgestelde moduleopzet (houd het klein)

```
/home/shared/l10n_sr_payroll/
├── __init__.py
├── __manifest__.py                  # depends: ['hr_payroll']  (+ 'hr_payroll_account' als je boekt)
├── data/
│   ├── hr_rule_parameter_data.xml   # §4 — alle parameters
│   ├── hr_payroll_structure_data.xml# structure type + structure (maandloon)
│   └── hr_salary_rule_data.xml      # §6 regeltabel
├── models/
│   ├── __init__.py
│   ├── sr_tax.py                    # pure Decimal-calculator, geen Odoo-afhankelijkheid
│   ├── hr_payslip.py                # 2 helpers: _sr_lb() en _sr_aov()
│   └── hr_contract.py               # of hr_version.py — 2 velden (zie hieronder)
└── tests/
    ├── __init__.py
    └── test_sr_payroll.py           # §8 gouden testgevallen
```

**Alle maatwerkvelden (houd het hierbij):**

| Model | Veld | Type | Waarom |
|---|---|---|---|
| contract/version | `sr_aantal_kinderen` | Integer | vrijstelling Art. 10h |
| contract/version | `sr_kinderbijslag_bedrag` | Monetary | bedrag kinderbijslag per periode |

Alles wat *bedragen per periode* is (transporttoelage, representatie, pensioenpremie,
ziektekostenpremie) doe je met **standaard Odoo-middelen**: `hr.payslip.input.type` +
inputs op de loonstrook, of standaard `hr.contract`-velden. Bouw géén eigen
`sr_vaste_regels` one2many zoals in de oude module.

**Salarisregeltabel (fase 1):**

| Seq | Code | Categorie | Berekening |
|---|---|---|---|
| 10 | `BASIC` | BASIC | contractloon per periode |
| 20 | `SR_ALW` | ALW | belastbare toelagen (payslip inputs, categorie belastbaar) |
| 21 | `SR_KB_BELAST` | ALW | kinderbijslag belastbaar surplus (Art. 10h) |
| 30 | `GROSS` | GROSS | `BASIC + ALW` |
| 50 | `SR_LB` | DED | `-payslip._sr_lb(GROSS, aftrek_bv)` |
| 60 | `SR_AOV` | DED | `-payslip._sr_aov(GROSS, aftrek_bv)` |
| 65 | `SR_AFTREK_BV` | DED | `-` pensioenpremie Art. 10f |
| 70 | `SR_INHOUDING` | DED | `-` overige inhoudingen (payslip inputs) |
| 80 | `SR_VRIJ` | eigen cat. `SR_VRIJ` | vrijgestelde vergoedingen (transport e.d.) |
| 81 | `SR_KB_VRIJ` | `SR_VRIJ` | kinderbijslag vrijgesteld deel |
| 250 | `NET` | NET | `BASIC + ALW + DED + SR_VRIJ` |

Let op de sequence van `NET`: **250**, hoger dan de standaard Odoo NET-regel (200),
zodat jouw formule wint en de vrijgestelde categorie meetelt.

## 7. Uitbetalen — dit moet aan het eind werken

De opdracht is expliciet "de payroll kan uitbetaald worden". Lever daarom een werkende
keten op, en kies met de gebruiker één van deze twee routes:

**Route A — standaard Odoo (aanbevolen, nul maatwerk).**
`hr.payslip.run` (loonrun) → loonstroken berekenen → bevestigen (`done`) →
`hr_payroll_account` maakt de journaalpost → betaling registreren via `account`.
Test dit end-to-end op de testdatabase en documenteer welke journalen/rekeningen
geconfigureerd moeten zijn.

**Route B — bankbestand (als de bank een bestand wil).**
Eén kleine wizard op `hr.payslip.run` die een CSV genereert met per werknemer:
naam, bankrekening, bedrag netto, valuta, omschrijving/periode.
De oude module ondersteunde DSB (CSV `;`), Hakrinbank (TXT tab), Finabank (CSV `,`),
Republic Bank (CSV `;`) en een generiek CSV-formaat. **Vraag de gebruiker welke bank
daadwerkelijk gebruikt wordt** en bouw alleen dat ene formaat — niet alle vijf.
Vereist dat werknemers een bankrekening hebben (Werknemer → Privé-informatie).

Lever hoe dan ook een **draaiboek** op: van werknemer aanmaken → contract/version →
loonrun → berekenen → controleren → bevestigen → uitbetalen.

## 8. Gouden testgevallen (moeten tot op de cent kloppen)

Schrijf deze als Odoo-tests (`--test-enable`). Ze komen uit de geverifieerde
2026-rekenvoorbeelden van de bestaande module.

### Testgeval 1 — referentiesalaris maandloon

Invoer: brutomaandloon **SRD 20.255,60**, maandloon (12 periodes), geen toelagen,
geen aftrek Art. 10f.

```
bruto_jaar       = 243.067,20
forfaitaire      = min(4 % × 243.067,20 = 9.722,69 ; 4.800) = 4.800,00
belastbaar_jaar  = 243.067,20 - 4.800 - 108.000 = 130.267,20
  schijf 1: 42.000    × 8 %  =  3.360,00
  schijf 2: 42.000    × 18 % =  7.560,00
  schijf 3: 42.000    × 28 % = 11.760,00
  schijf 4:  4.267,20 × 38 % =  1.621,54
lb_jaar          = 24.301,54
```

| Uitkomst | Verwacht |
|---|---|
| `GROSS` | 20.255,60 |
| `SR_LB` | **−2.025,13** |
| `SR_AOV` | **−794,22** |
| `NET` | **17.436,25** |

(AOV-grondslag = 20.255,60 − 400,00 = 19.855,60 → × 4 % = 794,22.)

### Testgeval 2 — samengesteld loon met toelagen en kinderbijslag

Invoer per maand: salaris 20.255,60 + kinderbijslag 500,00 + belastbare toelagen
1.300,00 + VGB 16,67 − fiscale aftrek kinderbijslag 212,50 → **bruto 21.859,77**.

| Uitkomst | Verwacht |
|---|---|
| `forfaitaire_jaar` | 4.800,00 |
| `belastbaar_jaar` | 149.517,24 |
| `lb_per_periode` | **2.634,71** |
| `aov_per_periode` | **858,39** |

### Testgeval 3 — randgevallen

- Bruto 0 → LB = 0 en AOV = 0, geen deling door nul, geen crash.
- Jaarloon onder de belastingvrije som (bijv. 8.000/maand → 96.000/jaar) → LB = 0.
- Loon exact op een schijfgrens → geen dubbeltelling in de aangrenzende schijf.
- `lb_per_periode == lb_jaar / periodes` (tot op de cent).
- Geen actieve heffingskorting: er mag geen HK-afslag in de LB zitten.

Referentiecommando (pas paden/db aan de container aan):
```bash
odoo-bin -d <testdb> -i l10n_sr_payroll --test-enable --stop-after-init --no-http --log-level=test
```

## 9. Werkwijze

1. Doe **Fase 0** en rapporteer de bevindingen (§2) terug voordat je bouwt —
   vooral: is `hr_payroll` aanwezig, en is het `hr.contract` of `hr.version`?
2. Bouw fase 1 (§3) in `/home/shared/l10n_sr_payroll`.
3. Installeer op een **verse testdatabase**, nooit op productie. Backup vooraf.
4. Laat de gouden tests uit §8 groen draaien. Rapporteer de echte output; als een test
   faalt, zeg dat, plak de output, en fix het — niet wegcommentariëren of skippen.
5. Draai één volledige loonrun end-to-end inclusief uitbetaling (§7).
6. Lever een kort `README.md` op met: installatie, waar de parameters staan en hoe je
   ze bij een wetswijziging aanpast (nieuw `.value`-record met nieuwe `date_from`), en
   het draaiboek van loonrun tot betaling.
7. Commit in `/home/shared` volgens de git-afspraken die daar gelden; als het geen
   git-repo is, vraag de gebruiker waar de code heen moet.

## 10. Randvoorwaarden

- **Niets in productie aanraken** zonder expliciete toestemming. Testdatabase, altijd.
- Geen wettelijke bedragen hardcoden in Python-formules: alles via `hr.rule.parameter`
  met `date_from`, zodat een wetswijziging in 2027 alleen een datarecord kost.
- `Decimal` + `ROUND_HALF_UP`, geen float-arithmetiek voor geld.
- Bij twijfel over een fiscale interpretatie: **vraag het, ga niet gokken.** Een fout
  in de LB-formule is een fout in iemands loonstrook.
- Meld het meteen als "minimaal" niet haalbaar blijkt voor een eis, in plaats van
  stilletjes de oude module na te bouwen.

### EINDE PROMPT

---

## Bijlage — waarom deze afbakening

De bestaande Odoo 18-module telt ~8.400 regels aan models + data en bevat veel
functionaliteit die voor "een loonrun kunnen draaien en uitbetalen" niet nodig is:
multi-currency met FX-lock per loonstrook, vijf bankformaten, een SQL-view voor fiscale
rapportage, verzamelloonstaat- en jaaropgave-wizards, drie loonstrook-layouts, een
in-app helppagina en een eigen `sr_vaste_regels`-mechanisme naast de standaard Odoo
payslip inputs.

Wat je fiscaal echt nodig hebt, is klein: ~20 parameterrecords, één salarisstructuur,
~11 salarisregels, één calculatorfunctie en twee extra contractvelden. Dat is de kern
die hierboven is uitgeschreven. De rest kan later, per stuk, als de gebruiker het vraagt.

## Bijlage — te beantwoorden vragen

Leg deze aan de gebruiker voor (de nieuwe sessie kan ze ook stellen):

1. **Odoo 19 Enterprise of Community?** Zonder Enterprise is er geen `hr_payroll` en
   verandert de opdracht fundamenteel.
2. **Welke bank** wordt gebruikt voor de salarisbetaling? (Bepaalt of route A of B in §7,
   en welk bestandsformaat.)
3. **Alleen maandloon**, of is FN-loon (26 periodes) ook nodig in fase 1?
4. **Overwerk (Art. 17c) en vakantietoelage/gratificatie (Art. 17)** — fase 1 of fase 2?
5. **Meerdere valuta** (USD/EUR-contracten) nodig, of is alles SRD?
6. **Wie bevestigt de 2026-bedragen** (belastingvrije som 108.000, schijven 42/84/126k,
   tarieven 8/18/28/38 %) tegen de officiële wettekst vóór de eerste echte uitbetaling?
