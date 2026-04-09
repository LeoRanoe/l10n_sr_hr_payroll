# Suriname Payroll — Design & Architecture Ruleset

**Version**: 1.0 | **Date**: 2026-04-09

This ruleset ensures the module is one unified, integrated part of Odoo.

---

## 1. NAMING CONVENTIONS

- **Models**: `hr.contract.sr.line.type` (Odoo dot-notation hierarchy)
- **Fields**: `sr_` prefix for SR-specific, snake_case (e.g., `sr_salary_type`)
- **Selection values**: lowercase semantic (`'belastbaar'`, not `'BT'`)
- **Files**: `models/hr_contract_sr_line_type.py` (follows model name)
- **XML IDs**: `sr_` prefix, descriptive (e.g., `sr_line_type_olie`)

## 2. MODEL DESIGN

- Use `_inherit` to extend existing models (never duplicate)
- Computed fields: `store=False` with `@api.depends(...)`
- One2many cascades: `ondelete='cascade'` on the inverse Many2one
- Every field has `string=` and `help=` text

## 3. CATEGORIES — Single Source of Truth

- Defined once in `models/sr_categorie.py`
- Base (3): `belastbaar`, `vrijgesteld`, `inhouding` → for contract lines
- Extended (7): + `overwerk`, `vakantie`, `gratificatie`, `bijz_beloning` → for payslip inputs

## 4. PARAMETERS — No Hardcoded Values

- All tax values in `hr.rule.parameter` (date-based)
- Access via `calc.fetch_params_from_rule_parameter()` or `calc.fetch_params_from_payslip()`
- Never use fallback defaults like `_p('CODE', 108000.0)`

## 5. CALCULATOR — Single Implementation

- All Article 14 logic in `models/sr_artikel14_calculator.py`
- Used by contract preview, payslip breakdown, and salary rules
- Pure functions, no Odoo model dependency

## 6. VIEW DESIGN

- Use `<xpath>` inheritance, never standalone form views
- Dynamic HTML fields for parameter-driven displays
- Menu hierarchy: Payroll → Configuratie → Suriname

## 7. DATA FILES

- Load order in `__manifest__.py`: security → structure → params → rules → types → views
- Every XML file has a comment header explaining purpose
- Records use clear `id=` prefix (`sr_line_type_`, `sr_param_`, etc.)

## 8. SECURITY

- Every model has ACL in `ir.model.access.csv`
- Users: read + write + create; Managers: + unlink
- Type model: users read-only, managers full access

## 9. TESTING

- Descriptive test names: `test_belastbaar_lijn_verhoogt_lb`
- Cover: bracket transitions, empty contracts, mixed categories, FN vs monthly
