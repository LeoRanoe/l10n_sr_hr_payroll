# Migratiehandleiding 2025 naar 2026

Deze handleiding is bedoeld voor beheerders die een bestaande Suriname payroll-omgeving opwaarderen naar de 2026 release van `l10n_sr_hr_payroll`.

## 1. Voorbereiding

1. Maak een volledige back-up van de Odoo-database en filestore.
2. Controleer dat de addoncode van `l10n_sr_hr_payroll` volledig is bijgewerkt.
3. Plan een korte payroll-freeze zodat er tijdens de update geen concept-loonstroken worden aangepast.

## 2. Module-update

Voer de module-update uit vanaf de Odoo servermap:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
.\odoo-bin -u l10n_sr_hr_payroll -d "Salarisverwerking-Module" --stop-after-init
```

## 3. Controleer de 2026 fiscale parameters

Ga naar `Payroll -> Configuratie -> Suriname -> SR Payroll Instellingen` en bevestig minimaal deze waarden:

- AKB per kind: `250.00`
- AKB maximum per maand: `1000.00`
- Bijzondere vrijstellingscap: `19500.00`
- AOV franchise per maand: `400.00`
- Heffingskorting: `750.00` (alleen audit / nog niet actief in Art. 14)

Let op:

- De AOV franchise geldt alleen voor `1 lb sal ovw` / maandloon.
- Voor `FN` past de payroll-engine automatisch geen franchise toe.

## 4. Hercontroleer alle actieve contracten

Open elk actief contract via `Suriname Payroll -> Fiscale Data` en controleer:

1. `Belastingtype` staat correct op `1 lb sal ovw` of `FN`.
2. `Aantal Kinderen` is tussen `0` en `4`.
3. Vaste toelagen en inhoudingen hebben de juiste fiscale categorie.
4. Kinderbijslag gebruikt het type `Kinderbijslag` en geen generieke vrije regel.

## 5. Controleer loonstrook-inputtypes

Bevestig dat bestaande payrollmedewerkers de juiste inputtypes blijven gebruiken:

- `SR_IN_OVERWERK` voor overwerk
- `SR_IN_VAKANTIE` voor vakantietoelage
- `SR_IN_GRAT` of `SR_IN_BONUS` voor gratificatie / bonus
- `SR_IN_BIJZ` voor bijzondere beloning
- `SR_IN_UITK_INEENS` voor Art. 17a uitkering ineens

## 6. FN 2026 controle

Voor contracten met `FN`:

1. Gebruik alleen de 26 ondersteunde 2026-FN perioden.
2. Maak geen vrije 14-daagse periode handmatig aan buiten de gedocumenteerde kalender.
3. Controleer bij de proefloonstrook dat de FN-indicator correct verschijnt.

## 7. Proefvalidatie

Voer minimaal deze controles uit voordat de release live gaat:

1. Maak een proefcontract met basisloon `SRD 20.255,60`.
2. Genereer een maandloon-loonstrook voor mei 2026.
3. Controleer dat de berekening conform het rekenvoorbeeld uit de context is.
4. Maak ook een FN-loonstrook om te bevestigen dat geen AOV franchise wordt toegepast.

## 8. Bekende 2026 gedragsregels

- Negatieve lonen, negatieve SR-inputs en negatieve vaste SR-regels worden geblokkeerd.
- AKB is gemaximeerd op `4` kinderen in de contractlaag.
- Heffingskorting wordt opgeslagen voor audit, maar niet actief toegepast in de Art. 14 engine.
- De actuele payroll-engine leest eerst `SR Payroll Instellingen` en valt pas daarna terug op `hr.rule.parameter`.

## 9. Naverificatie

Na de update:

1. Open de help-pagina via `Payroll -> Suriname -> Help & Documentatie`.
2. Controleer de contracttab `Suriname Payroll`.
3. Draai de addon-validatie met tests als onderdeel van de releasecheck.