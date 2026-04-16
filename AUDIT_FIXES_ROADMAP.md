# Suriname Payroll Module (l10n_sr_hr_payroll) - Audit Fixes Roadmap

**Datum**: 16 april 2026  
**Module**: l10n_sr_hr_payroll  
**Context**: Comprehensive audit tegen Loonbelasting context document

---

## 📋 Overzicht

Dit document bevat alle geïdentificeerde problemen uit de audit met prioriteiten en concrete fixes.

| Status | Count | Details |
|--------|-------|---------|
| **P1 CRITICAL** | 1 | Heffingskorting inconsistentie |
| **P2 HIGH** | 2 | Help dynamiek + Kinderbijslag presentatie |
| **P3 MAINTENANCE** | 2 | Code duplicatie + Fallback logica |
| **TOTAL ISSUES** | 7 | Alle issues opgelost in roadmap |

---

## 🔴 P1 - CRITICAL: Heffingskorting (Tax Credit) Inconsistentie

### 📍 Probleem
**Locatie**: 4 verschillende bestanden met conflicterende informatie

| Bestand | Lijn | Status |
|---------|------|--------|
| `sr_artikel14_calculator.py` | 97 | "geen heffingskorting" - NIET TOEGEPAST |
| `hr_salary_rule_data.xml` | 382 | `active="False"` - VERVALLEN |
| `hr_rule_parameter_data.xml` | ~350 | Bestaat nog - PARAMETER LEEFT |
| `sr_help_template.xml` | ~295 | Nog vermeld in parameter list |

**Impact**: Gebruikers zien parameter in configuratie maar het heeft GEEN effect op loonstrook.

### ✅ Fix Strategy: VOLLEDIG VERWIJDEREN

#### Stap 1: Verwijder parameter uit hr_rule_parameter_data.xml
**Bestand**: `data/hr_rule_parameter_data.xml`  
**Actie**: Zoek en verwijder deze records:
```xml
<record id="sr_heffingskorting_maand_2026" model="hr.rule.parameter.value">
    <field name="parameter_id" ref="sr_heffingskorting_maand"/>
    <field name="date_from">2026-01-01</field>
    <field name="value">750</field>
</record>

<record id="sr_heffingskorting_maand" model="hr.rule.parameter">
    <field name="code">SR_HEFFINGSKORTING_MAAND</field>
    <field name="country_id" ref="base.sr"/>
    <field name="description">Maandelijks heffingskorting (TAX CREDIT) - VERVALLEN</field>
</record>
```

**Verificatie**: Controleer dat deze ID's niet meer voorkomen in het bestand:
- `sr_heffingskorting_maand`
- `sr_heffingskorting_maand_2026`

#### Stap 2: Verwijder/markeer the salary rule
**Bestand**: `data/hr_salary_rule_data.xml`  
**Locatie**: Regel 55 (SR_HK)  
**Huidge status**: `active="False"` met comment "VERVALLEN"  
**Actie**: VERWIJDER de gehele regel-definitie (niet alleen deactiveren):

```xml
<!-- DELETE THIS ENTIRE BLOCK: -->
<record id="sr_hk_rule" model="hr.salary.rule">
    <field name="sequence">55</field>
    <field name="name">Heffingskorting (Tax Credit)</field>
    <field name="code">SR_HK</field>
    <field name="description">VERVALLEN - no longer applied</field>
    <field name="active">False</field>
    <!-- ... rest of rule ... -->
</record>
```

**Reden**: Regel is toch al inactief; volledige verwijdering verwijdert verwarring.

#### Stap 3: Verwijder hardcoded referenties uit documentatie
**Bestand**: `views/sr_help_template.xml`  
**Locaties met "heffingskorting"**: Zoek en controleer alle verwijzingen  
**Actie**: Verwijder secties die heffingskorting voorstellen als actief systeem

**Naar stap 4 gaan**: Update calculator comentaar

#### Stap 4: Controleer calculator
**Bestand**: `models/sr_artikel14_calculator.py`  
**Huidge status**: Line 97 zegt al `# geen heffingskorting` (correct)  
**Actie**: GEEN WIJZIGING NODIG - calculator is al correct

**Verificatie**: Run tests
```bash
cd "C:\Program Files\Odoo 18.0e.20260407\server"
python odoo-bin --test-enable --test-tags=l10n_sr -d "Salarisverwerking-Module" \
  --addons-path="..." --stop-after-init --no-http
```

---

## 🟠 P2 - HIGH: Help Documentatie Dynamisch Maken

### 📍 Probleem
**Locatie**: `views/sr_help_template.xml`

| Lijn | Hardcoded Waarde | Bron |
|------|------------------|------|
| 333 | "4% van bruto, max SRD 4.800" | SR_FORFAITAIRE_PCT + SR_FORFAITAIRE_MAX_JAAR |
| 339 | "SRD 108.000/jaar" | SR_BELASTINGVRIJ_JAAR |
| 353 | "8% / 18% / 28% / 38%" | SR_TARIEF_1-4 |
| 359 | "franchise SRD 400" | SR_AOV_FRANCHISE_MAAND |
| 377-380 | Belastingschijf tabel | SR_SCHIJF_1-3_GRENS + SR_TARIEF_1-4 |
| 433 | "Max SRD 125 per kind, max SRD 500" | SR_KINDBIJ_MAX_KIND + SR_KINDBIJ_MAX_MAAND |

**Impact**: Na wetswijziging blijft oude waarden in help staan terwijl parameters al gewijzigd zijn.

### ✅ Fix: Drie delen

#### Deel A: Pass extra parameters uit controller
**Bestand**: `controllers/main.py`  
**Huidge code**: 
```python
@http.route('/sr_payroll/help', type='http', auth='user')
def sr_payroll_help(self):
    params = {
        'SR_BELASTINGVRIJ_JAAR': {...},
        ...
    }
    return request.render('l10n_sr_hr_payroll.sr_help_template', {'params': params})
```

**Wijziging NODIG**:
```python
# IN ADDITION TO params dict, ALSO compute:
formatted_params = {
    'forfaitaire_text': f"4% van bruto, max SRD {params['SR_FORFAITAIRE_MAX_JAAR']:,.0f}/jaar",
    'belastingvrij_text': f"SRD {params['SR_BELASTINGVRIJ_JAAR']:,.0f}/jaar",
    'aov_franchise_text': f"franchise SRD {params['SR_AOV_FRANCHISE_MAAND']:,.0f}",
    'kinderbijslag_text': f"Max SRD {params['SR_KINDBIJ_MAX_KIND_MAAND']:,.0f} per kind, max SRD {params['SR_KINDBIJ_MAX_MAAND']:,.0f} totaal per maand",
}
return request.render('...', {
    'params': params,
    'formatted_params': formatted_params,
})
```

#### Deel B: Update help template references
**Bestand**: `views/sr_help_template.xml`

**Verandering 1 - Lijn 333** (professionele kosten):
```xml
<!-- VAN: -->
<p class="lead">4% van bruto, max SRD 4.800/jaar</p>

<!-- NAAR: -->
<p class="lead" t-out="formatted_params.get('forfaitaire_text', '...')"></p>
```

**Verandering 2 - Lijn 339** (belastingvrij bedrag):
```xml
<!-- VAN: -->
SRD 108.000/jaar (SRD 9.000/maand)

<!-- NAAR: -->
<t t-out="formatted_params.get('belastingvrij_text', '...')"/> (SRD <t t-out="'{:,.0f}'.format(params['SR_BELASTINGVRIJ_JAAR']/12)"/>)
```

**Verandering 3 - Lijn 353** (belastingpercentages):
```xml
<!-- VAN: -->
Progressief: 8% / 18% / 28% / 38%

<!-- NAAR: -->
Progressief: <t t-out="'{:.0%} / {:.0%} / {:.0%} / {:.0%}'.format(
  float(params['SR_TARIEF_1']),
  float(params['SR_TARIEF_2']),
  float(params['SR_TARIEF_3']),
  float(params['SR_TARIEF_4'])
)"/>
```

**Verandering 4 - Lijn 359** (AOV franchise):
```xml
<!-- VAN: -->
4% over (bruto − franchise SRD 400)

<!-- NAAR: -->
4% over (bruto − <t t-out="formatted_params.get('aov_franchise_text', 'franchise SRD 400')"/>)
```

**Verandering 5 - Lijn 377-380** (belastingschijf tabel):
```xml
<!-- VAN: hardcoded tabel -->
<table>
  <tr><td>1</td><td>SRD 0</td><td>SRD 42.000</td><td>8%</td></tr>
  <tr><td>2</td><td>SRD 42.000</td><td>SRD 84.000</td><td>18%</td></tr>
  <tr><td>3</td><td>SRD 84.000</td><td>SRD 126.000</td><td>28%</td></tr>
  <tr><td>4</td><td>SRD 126.000</td><td>∞</td><td>38%</td></tr>
</table>

<!-- NAAR: dynamisch gegenereerd -->
<t t-set="bd" t-value="env['sr.artikel14.calculator'].generate_tax_bracket_html(params)"/>
<t t-raw="bd"/>
```

**Verandering 6 - Lijn 433** (kinderbijslag limieten):
```xml
<!-- VAN: -->
Max SRD 125 per kind, max SRD 500 totaal per maand

<!-- NAAR: -->
<t t-out="formatted_params.get('kinderbijslag_text', 'Max SRD 125 per kind, max SRD 500 totaal per maand')"/>
```

#### Deel C: Test changes
```bash
# Open help pagina in browser:
# http://localhost:8069/sr_payroll/help

# Wijzig een parameter in Odoo UI en herlaad help
# Controleer dat nieuwe waarde direct verschijnt
```

---

## 🟡 P2 - MEDIUM: Kinderbijslag Presentatie Splitsen

### 📍 Probleem
**Locatie**: `reports/report_payslip_sr.xml` lijn 126

Kinderbijslag wordt als ÉÉN regel weergegeven:
```
Kinderbijslag (belastingvrij): SRD 250
```

Maar backend splitst het in twee delen:
- `kb_belastbaar`: SRD 75 (WEL belast)
- `kb_vrijgesteld`: SRD 175 (NIET belast)

**Impact**: Gebruiker denkt hele bedrag is belastingvrij; audit trail ontbreekt.

### ✅ Fix

#### Stap 1: Expand breakdown dict in hr_payslip.py
**Bestand**: `models/hr_payslip.py` (~lijn 120)  
**Huidge code**:
```python
def _get_sr_artikel14_breakdown(self):
    bd = {...}
    bd['kinderbijslag'] = bd.get('kb_belastbaar', 0) + bd.get('kb_vrijgesteld', 0)
    return bd
```

**Wijziging**: EXPLICIETER LABELS TOEVOEGEN
```python
def _get_sr_artikel14_breakdown(self):
    bd = {...}
    # Already splits into kb_belastbaar and kb_vrijgesteld separately
    # Just ensure both keys are present for reporting
    bd['kinderbijslag_belastbaar'] = bd.get('kb_belastbaar', 0)
    bd['kinderbijslag_vrijgesteld'] = bd.get('kb_vrijgesteld', 0)
    bd['kinderbijslag_totaal'] = (
        bd.get('kb_belastbaar', 0) + bd.get('kb_vrijgesteld', 0)
    )
    return bd
```

#### Stap 2: Update report template
**Bestand**: `reports/report_payslip_sr.xml` lijn 126

**VAN**:
```xml
<tr>
    <td>Kinderbijslag</td>
    <td class="text-end">
        <t t-esc="'SRD {:,.2f}'.format(bd.get('kinderbijslag', 0))"/>
    </td>
    <td class="text-muted">(belastingvrij)</td>
</tr>
```

**NAAR**:
```xml
<!-- Kinderbijslag - belastingvrij deel -->
<tr>
    <td>Kinderbijslag (belastingvrij)</td>
    <td class="text-end">
        <t t-esc="'SRD {:,.2f}'.format(bd.get('kinderbijslag_vrijgesteld', 0))"/>
    </td>
    <td class="text-muted">(Art. 10h)</td>
</tr>
<!-- Kinderbijslag - belastbaar deel -->
<tr>
    <td>Kinderbijslag (belastbaar)</td>
    <td class="text-end">
        <t t-esc="'SRD {:,.2f}'.format(bd.get('kinderbijslag_belastbaar', 0))"/>
    </td>
    <td class="text-muted">(inbegrepen in schijven)</td>
</tr>
```

#### Stap 3: Update reference table in contract view
**Bestand**: `views/hr_contract_views.xml`  
**Huidge code**: Toont kinderbijslag als enkele waarde in preview  
**Wijziging**: TWEE VELDEN TONEN
```xml
<!-- VAN: één field -->
<field name="sr_preview_kinderbijslag" widget="monetary"/>

<!-- NAAR: twee fields (aangepast in model) -->
<field name="sr_preview_kinderbijslag_belastingvrij" widget="monetary"/>
<field name="sr_preview_kinderbijslag_belastbaar" widget="monetary"/>
```

#### Stap 4: Update contract preview computed fields
**Bestand**: `models/hr_contract.py` lijn 130  
**Wijziging**: Voeg twee split-velden toe aan computed fields

```python
# In hr_contract.py, @api.depends decorator:
@api.depends(
    'sr_salary_type', 'sr_aantal_kinderen', 
    'sr_vaste_regels', 'salary_structure_id'
)
def _compute_sr_preview(self):
    # Existing code...
    bd = payslip._get_sr_artikel14_breakdown()
    
    # Add split fields
    self.sr_preview_kinderbijslag_vrij = bd.get('kinderbijslag_vrijgesteld', 0)
    self.sr_preview_kinderbijslag_belastbaar = bd.get('kinderbijslag_belastbaar', 0)
```

**Verificatie**: Contract preview toont nu twee apart bedragen voor kinderbijslag.

---

## 🟣 P3 - MAINTENANCE: Duplicated Art. 17 Logic Consolideren

### 📍 Probleem
**Locatie**: `data/hr_salary_rule_data.xml`

| Regel | Locatie | Logica |
|-------|---------|--------|
| SR_LB_BIJZ | ~Lijn 850 | Art. 17 marginaal method |
| SR_AOV_BIJZ | ~Lijn 900 | Identieke logica |

**Code volume**: 80+ lines Python per regel = duplicatie & moeilijk onderhoud

**Impact**: Bugfix of rate-wijziging vereist updaten van beide rules → makkelijk een te missen.

### ✅ Fix: Extract naar reusable function

#### Stap 1: Create new calculator function
**Bestand**: `models/sr_artikel14_calculator.py`  
**Actie**: Voeg deze functie toe (na `calculate_lb`):

```python
@staticmethod
def calculate_special_bonus_tax(
    special_amount, 
    salary_ytd,  # year-to-date salary
    params,
    bonus_type='LB'  # 'LB' or 'AOV'
):
    """
    Calculate tax for special bonuses using marginaal tarief method.
    
    Args:
        special_amount: Bedrag van de speciale uitkering (e.g., vakantie, bonus)
        salary_ytd: Totaal salaris tot nu toe dit jaar (excl. bonus)
        params: Dictionary met parameter waarden
        bonus_type: 'LB' (belasting) of 'AOV' (pensoen)
    
    Returns:
        Dictionary met {
            'bruto': special_amount,
            'belastbaar': special_amount (usually),
            'tax_or_contribution': calculated amount
        }
    """
    
    # Determine ceiling based on type
    if bonus_type == 'LB':
        ytd_ceiling = params.get('SR_17_CEILING_JAAR', 500000)  # Very high
        bracket_params = ['SR_17_SCHIJF_1_GRENS', 'SR_17_SCHIJF_2_GRENS', 'SR_17_SCHIJF_3_GRENS']
        tariff_params = ['SR_17_TARIEF_1', 'SR_17_TARIEF_2', 'SR_17_TARIEF_3', 'SR_17_TARIEF_4']
    else:  # AOV
        ytd_ceiling = params.get('SR_AOV_BONUS_CEILING_JAAR', 126000)
        bracket_params = ['SR_AOV_BONUS_SCHIJF_1', 'SR_AOV_BONUS_SCHIJF_2']
        tariff_params = ['SR_AOV_BONUS_TARIEF_1', 'SR_AOV_BONUS_TARIEF_2', 'SR_AOV_BONUS_TARIEF_3']
    
    # Check if ytd already exceeds ceiling
    if salary_ytd >= ytd_ceiling:
        return {
            'bruto': special_amount,
            'belastbaar': special_amount,
            'tax_or_contribution': special_amount * float(tariff_params[-1])  # highest rate
        }
    
    # Room available under ceiling
    room = ytd_ceiling - salary_ytd
    taxable_portion = min(special_amount, room)
    excess_portion = special_amount - taxable_portion
    
    # Apply brackets to taxable portion
    tax = Ar14Calculator._apply_brackets(
        taxable_portion,
        bracket_params,
        tariff_params,
        params
    )
    
    # Excess gets highest bracket rate
    if excess_portion > 0:
        tax += excess_portion * float(params.get(tariff_params[-1], 0))
    
    return {
        'bruto': special_amount,
        'belastbaar': special_amount,
        'tax_or_contribution': tax
    }

@staticmethod
def _apply_brackets(amount, bracket_param_names, tariff_param_names, params):
    """Helper to apply bracket logic."""
    # This extracts the bracket logic from existing calculate_lb
    # Implementation similar to lines 115-130 in current code
    ...
```

#### Stap 2: Update salary rules
**Bestand**: `data/hr_salary_rule_data.xml`

**Regel 91 (SR_LB_BIJZ)** - VAN:
```xml
<field name="code_compute_expression">
# 80+ lines van bracket logica
result = ...  # complex calculation
</field>
```

**NAAR**:
```xml
<field name="code_compute_expression">
from odoo.addons.l10n_sr_hr_payroll.models.sr_artikel14_calculator import Ar14Calculator

params = payslip._fetch_sr_params()
salary_ytd = payslip._compute_salary_ytd()

result = Ar14Calculator.calculate_special_bonus_tax(
    special_amount=categories['GROSS'],
    salary_ytd=salary_ytd,
    params=params,
    bonus_type='LB'
)['tax_or_contribution']
</field>
```

**Regel 92 (SR_AOV_BIJZ)** - Identieke wijziging met `bonus_type='AOV'`

#### Stap 3: Verify deduplication
**Test**:
```bash
# Run tests for special bonuses
python odoo-bin --test-enable --test-tags=special_bonus -d "..." --stop-after-init --no-http
```

---

## 🟣 P3 - HYGIENE: Kinderbijslag Fallback Logica Verwijderen

### 📍 Probleem
**Locatie**: `models/hr_contract.py` lijn 206

```python
def _sr_kinderbijslag_split(max_kind_maand=125.0, max_maand=500.0):
    """
    Hardcoded defaults embedded in function signature
    """
```

**Impact**: Fallback happens silently; no error if parameter lookup fails.

### ✅ Fix: Require explicit parameters

**Bestand**: `models/hr_contract.py`

**VAN**:
```python
def _sr_kinderbijslag_split(self, max_kind_maand=125.0, max_maand=500.0):
    """Split child allowance into taxable/exempt"""
    # Uses defaults silently if parameter fetch fails
    ...
```

**NAAR**:
```python
def _sr_kinderbijslag_split(self, max_kind_maand=None, max_maand=None):
    """
    Split child allowance into taxable/exempt.
    
    Args:
        max_kind_maand: Max per child (SRD). If None, fetches from SR_KINDBIJ_MAX_KIND_MAAND
        max_maand: Max total (SRD). If None, fetches from SR_KINDBIJ_MAX_MAAND
    
    Raises:
        ValueError: If parameters not found and no explicit values provided
    """
    
    if max_kind_maand is None:
        params = self.env['hr.rule.parameter'].sudo().search([
            ('code', '=', 'SR_KINDBIJ_MAX_KIND_MAAND'),
            ('country_id', '=', self.env.ref('base.sr').id)
        ])
        if not params:
            raise ValueError(
                "SR_KINDBIJ_MAX_KIND_MAAND parameter not found. "
                "Set it in HR > Payroll Configuration"
            )
        max_kind_maand = params._get_parameter_value(
            self.contract_id.date_start
        )
    
    if max_maand is None:
        params = self.env['hr.rule.parameter'].sudo().search([
            ('code', '=', 'SR_KINDBIJ_MAX_MAAND'),
            ('country_id', '=', self.env.ref('base.sr').id)
        ])
        if not params:
            raise ValueError(
                "SR_KINDBIJ_MAX_MAAND parameter not found. "
                "Set it in HR > Payroll Configuration"
            )
        max_maand = params._get_parameter_value(
            self.contract_id.date_start
        )
    
    # Rest of calculation (no fallback, explicit parameters required)
    ...
```

**Update call sites**: Alle plaatsen waar deze functie wordt aangeroepen:

```python
# IN CONTRACT PREVIEW SECTION (line ~130):
# VAN:
kb_vrij, kb_belast = self._sr_kinderbijslag_split()  # silent defaults

# NAAR:
try:
    kb_vrij, kb_belast = self._sr_kinderbijslag_split()
except ValueError as e:
    # Show error in preview
    self.sr_preview_kinderbijslag_vrij = 0
    self.sr_preview_kinderbijslag_belastbaar = 0
    _logger.warning(f"Kinderbijslag calculation error: {e}")
    return
```

---

## 🧪 Test Matrix After All Fixes

### Unit Tests (verify each fix doesn't break existing functionality)

| Test | File | Command |
|------|------|---------|
| Heffingskorting removed | `tests/test_article_14.py` | Assert that no heffingskorting appears in payslip |
| Help template renders | `tests/test_help_page.py` | Load `/sr_payroll/help`, verify no hardcoded values, check params render |
| Kinderbijslag split display | `tests/test_payslip.py` | Assert report shows both kb_belastbaar and kb_vrijgesteld |
| Special bonus consolidation | `tests/test_article_17.py` | Verify SR_LB_BIJZ and SR_AOV_BIJZ produce same results as before |
| Kinderbijslag no fallback | `tests/test_contract.py` | Call `_sr_kinderbijslag_split()` without params, verify ValueError raised |

### Integration Tests

```bash
cd "C:\Program Files\Odoo 18.0e.20260407\server"

# Run complete test suite
python odoo-bin \
  --test-enable \
  --test-tags=l10n_sr_hr_payroll \
  -d "Salarisverwerking-Module" \
  --addons-path="c:\program files\odoo 18.0e.20260407\server\odoo\addons,c:\program files\odoo 18.0e.20260407\sessions\addons\18.0" \
  --logfile= \
  --stop-after-init \
  --no-http
```

**Expected result**: All tests pass (currently 82 tests, 0 failures)

---

## 📋 Implementation Checklist

### Phase 1: P1 CRITICAL (Do first)
- [ ] Delete heffingskorting parameter records from hr_rule_parameter_data.xml
- [ ] Delete or archive heffingskorting salary rule from hr_salary_rule_data.xml
- [ ] Remove heffingskorting references from sr_help_template.xml
- [ ] Run basic tests to verify payslip still calculates correctly
- [ ] **Commit**: "Fix: Remove obsolete heffingskorting (tax credit) completely"

### Phase 2: P2 HIGH (Do next)
- [ ] Add `formatted_params` dict to controllers/main.py
- [ ] Update sr_help_template.xml to use dynamic parameters (6 locations)
- [ ] Update hr_payslip.py breakdown dict to include split kinderbijslag fields
- [ ] Update sr.xml report template to show two kinderbijslag lines
- [ ] Update contract preview computed fields for split display
- [ ] Test help page shows current parameters dynamically
- [ ] Test payslip report shows split kinderbijslag
- [ ] **Commit 2a**: "Feat: Make help documentation parameter-driven"
- [ ] **Commit 2b**: "Feat: Split kinderbijslag display on payslip report"

### Phase 3: P3 MAINTENANCE (Do next)
- [ ] Extract `calculate_special_bonus_tax()` in sr_artikel14_calculator.py
- [ ] Update SR_LB_BIJZ rule to call new function
- [ ] Update SR_AOV_BIJZ rule to call new function
- [ ] Test special bonus calculations produce identical results
- [ ] **Commit 3a**: "Refactor: Consolidate Art. 17 bonus tax logic"

### Phase 4: P3 HYGIENE (Do last)
- [ ] Update `_sr_kinderbijslag_split()` to require explicit parameters
- [ ] Update all call sites to pass explicit parameters or handle ValueError
- [ ] Test ValueError raised when parameters missing
- [ ] **Commit 3b**: "Refactor: Remove kinderbijslag parameter fallback logic"

### Phase 5: Final Verification
- [ ] Run complete test suite (82 tests)
- [ ] Manual test: Create contract, verify preview shows correct values
- [ ] Manual test: Create payslip, verify report shows all calculations
- [ ] Manual test: Load help page, modify a parameter, reload help to see change
- [ ] Update AUDIT_STATUS.md with "ALL FIXES IMPLEMENTED" + date

---

## 📞 Questions During Implementation?

Refer back to:
- **Line numbers**: All references include file path + line number
- **Code snippets**: Shows exact VAN/NAAR format
- **Test commands**: Ready-to-run bash commands for Windows PowerShell
- **File structure**: Follows Odoo module conventions

---

## ✅ Success Criteria

After all fixes implemented:

| Criteria | Verification |
|----------|---------------|
| **Zero hardcoded values** | grep finds no "8%", "18%", "28%" in help template (only parameters) |
| **No heffingskorting** | Parameter does not exist; rule does not exist; calc ignores it |
| **Help dynamic** | Modify param, reload help page, see new value immediately |
| **Kinderbijslag transparent** | Payslip shows both belastbaar and vrijgesteld separately |
| **No silent fallbacks** | `_sr_kinderbijslag_split()` raises ValueError if params missing |
| **No duplication** | SR_LB_BIJZ and SR_AOV_BIJZ each call single `calculate_special_bonus_tax()` |
| **All tests pass** | `Ran 82 tests ... OK` (or more tests after adding new ones) |

---

**Prepared**: 16 april 2026  
**Status**: Ready for implementation  
**Priority Order**: P1 → P2 → P3 → Testing & Validation
