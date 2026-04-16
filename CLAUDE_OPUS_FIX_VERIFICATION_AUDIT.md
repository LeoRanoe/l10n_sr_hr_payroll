# Payroll Fix Verification Audit

Date: 2026-04-16
Module: l10n_sr_hr_payroll
Source of truth: Salarisverwerking Module/Loonbelasting context.md

## Scope

This audit verifies two things:

1. Whether the earlier Claude fixes actually made the payroll logic fiscally consistent with Loonbelasting context.md.
2. Whether the values produced in the backend reach the user-facing Odoo UI unchanged and under the correct labels.

Validation performed:

- Static code audit of the calculator, salary rules, contract preview, payslip breakdown, report QWeb, help/config UI, and tests.
- Runtime module upgrade check via:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
& "c:\Program Files\Odoo 18.0e.20260407\python\python.exe" odoo-bin -u l10n_sr_hr_payroll -d "Salarisverwerking-Module" --addons-path="c:\program files\odoo 18.0e.20260407\server\odoo\addons,c:\program files\odoo 18.0e.20260407\sessions\addons\18.0" --logfile= --stop-after-init --no-http
```

Runtime result:

- Module upgrade currently fails.
- First blocking error:
  - views/hr_contract_views.xml still references sr_preview_hk_periode
  - model hr.contract no longer defines that field

## Audit of Previous Fixes

Overall verdict:

- The core fiscal engine is much closer to the source context than before.
- The implementation is not 100% complete end-to-end.
- The remaining errors are now mostly integration, UI mapping, stale rule/config, and regression-test gaps.

### Fix-by-fix status

| Area | Expected per context | Current status | Verdict |
|---|---|---|---|
| Art. 14 normal LB engine | Annualize -> Art. 10f deduction -> forfaitaire aftrek -> belastingvrije som -> 8/18/28/38 -> divide back by period | models/sr_artikel14_calculator.py now follows that order and no longer subtracts HK inside calculate_lb() | Correct |
| Heffingskorting removal | No active HK path if formulas/example remain leading source | Core calculator removed HK, but SR_HK salary rule, help/config UI, manifest text, and one view still keep HK alive | Not complete |
| Art. 17 LB marginal method | One combined belastbaar_bijz_totaal, one delta, no x 12/26 multiplier | SR_LB_BIJZ now combines inputs and uses one marginal delta without multiplying by periodes | Correct |
| Art. 17 AOV | Difference per period, not 4% of full bonus amount | SR_AOV_BIJZ now uses (belastbaar_bijz_totaal / periodes) * aov_tarief | Correct |
| Vakantietoelage exemption | min(2 x basisloon, remaining year cap) | Implemented in SR_LB_BIJZ and SR_AOV_BIJZ | Correct |
| Year cap for vakantie/gratificatie | Enforce annual cap across multiple slips | YTD lookup exists, but recomputes historic usage with current contract wage/date_start instead of reading the actual old exemption used | Partially correct |
| Art. 17a support | Separate input type, separate brackets, no belastingvrije som, AOV 4% on full amount | Input type, parameters, LB rule and AOV rule are present | Correct |
| Kinderbijslag zero children | Full amount taxable when no children are registered | hr_contract._sr_kinderbijslag_split() now returns belastbaar=total_kb, vrijgesteld=0.0 | Correct |
| Preview parameter source | Use hr.rule.parameter instead of hardcoded 125/500 | _compute_sr_preview() now loads SR_KINDBIJ_MAX_KIND_MAAND and SR_KINDBIJ_MAX_MAAND | Correct |
| Breakdown/report parity | Report should mirror actual payroll output | Improved, but still reconstructs an incomplete earnings story and can diverge from actual NET and visible line items | Partially correct |
| Tests | Remove old HK logic and add risky-path coverage | Main Art. 14 tests were updated, but stale HK references remain in tests/test_improvements.py and the new risky paths are still not covered | Partially correct |

## Fiscal Logic Findings

### What is now correct

1. The Art. 14 calculator now uses the correct step order and correct bracket math for normal salary.
2. The AOV logic now matches the context for monthly vs FN:
   - monthly: 4% after SRD 400 franchise
   - FN: 4% with no franchise
3. The Art. 17 path is materially improved:
   - multiple bijzondere beloningen are combined
   - the marginal delta is no longer multiplied by 12 or 26
   - AOV on bijzondere beloningen is now per-timevak delta based
4. The Art. 17a path exists and uses separate bracket logic.

### Important nuance about heffingskorting

Loonbelasting context.md is internally inconsistent:

- Some narrative/constants still mention heffingskorting.
- The actual Art. 14 formulas and worked formula path do not subtract it.

The code fix chose the formula path as source of truth. That makes the calculator internally consistent, but the repository still contains multiple stale UI/config/help surfaces that tell the user the opposite.

### Remaining fiscal defect in the YTD cap logic

The new YTD cap implementation is directionally correct, but not historically safe.

Current problem in SR_LB_BIJZ and SR_AOV_BIJZ:

- previous-slip usage is recalculated using the current contract's wage_maand
- previous-slip usage is recalculated using the current contract.date_start
- this can misstate already-used exemption if wage or contract conditions changed mid-year

Safer approach:

- read the actual exempt amount already applied on prior slips
- or persist exemption usage explicitly
- do not recompute past usage from the current contract state

## Data Integrity Map

There is no custom JSON payroll API in this module.

The payroll "frontend" is primarily:

- Odoo form/list views bound directly to ORM fields
- QWeb payslip report templates bound to dict values from _get_sr_artikel14_breakdown()
- one help page rendered by controllers/main.py via request.render()

No client-side JavaScript recalculation was found in static/.

That means discrepancies are server-side mapping/documentation problems, not browser math bugs.

### 1. Contract preview numeric fields

Backend source:

- models/hr_contract.py::_compute_sr_preview()
- Fields set directly:
  - sr_preview_bruto
  - sr_preview_belastbaar_jaar
  - sr_preview_lb_periode
  - sr_preview_aov_periode
  - sr_preview_netto

Frontend surface:

- views/hr_contract_views.xml
- Displayed through readonly monetary fields

Integrity verdict:

- The surviving numeric fields are direct backend-to-UI bindings.
- No browser-side recalculation is happening.
- But the view still contains sr_preview_hk_periode, which now breaks module loading.

Result:

- The intended values would display unchanged.
- The screen itself is currently not upgrade-safe because it references a removed field.

### 2. Contract preview debug panel

Backend source:

- models/hr_contract.py sets sr_preview_breakdown_html via calc.generate_breakdown_html(...)

Frontend surface:

- views/hr_contract_views.xml field sr_preview_breakdown_html

Integrity verdict:

- This is not a passive display of sr_preview_* values.
- The helper recomputes its own net presentation.
- That recomputation does not include belastbare toelagen in the final net row.

Concrete discrepancy:

- sr_preview_netto in hr_contract.py uses bruto_totaal = wage + belastbaar_toelagen + kb_belastbaar + kb_vrijgesteld + vrijgesteld_toelagen
- generate_breakdown_html() uses a separate net formula based on wage + kb + vrijgesteld - deductions
- belastbaar_toelagen are missing from the HTML net reconstruction

Effect:

- The preview number field can be correct while the debug panel shows a different net story.

### 3. Payslip report data path

Backend source:

- models/hr_payslip.py::_get_sr_artikel14_breakdown()
- Returns dict bd

Frontend surface:

- reports/report_payslip_sr.xml
- QWeb reads bd.get(...)

Integrity verdict:

- The report displays whatever bd contains; there is no extra client-side calculation.
- The problem is that bd is still only a partial reconstruction of the real payslip.

What is good:

- LB and AOV component totals are now read from actual line_ids for:
  - SR_LB
  - SR_LB_BIJZ
  - SR_LB_17A
  - SR_LB_OWK
  - SR_AOV
  - SR_AOV_BIJZ
  - SR_AOV_17A
  - SR_AOV_OWK

What still diverges:

- bd['kinderbijslag'] adds SR_KINDBIJ even though SR_KINDBIJ is actually "Vaste Vrijgestelde Vergoedingen (Contract)", not child benefit
- bruto_totaal does not include post-GROSS positive earnings like overwerk, vakantie, gratificatie, bijzondere beloning, and uitkering ineens
- netto is therefore not guaranteed to match the real NET salary rule when those earnings exist
- the report summary omits aftrek_bv even though bd['netto'] subtracts it

Effect:

- The report can show a backend value exactly, but still tell the wrong story about how that value was built.

### 4. Help and config UI

Backend source:

- controllers/main.py builds params dict for the help page
- hr.rule.parameter list/search views expose payroll config

Frontend surface:

- views/sr_help_template.xml
- views/hr_payroll_config_sr_views.xml

Integrity verdict:

- These are direct displays of server-side metadata.
- They do not affect payroll results directly.
- They do misinform the user about what the system is doing.

Current stale outputs:

- help page still advertises heffingskorting as step 6 in the salary flow
- help page FAQ still says the system applies SR_HEFFINGSKORTING_MAAND
- config search filter still groups SR_HEFFINGSKORTING_MAAND under Art. 14 parameters
- config help text still describes HK as an active deduction path

## Discrepancies

### Critical discrepancies

1. Module upgrade fails because views/hr_contract_views.xml still references sr_preview_hk_periode.
2. data/hr_salary_rule_data.xml still defines SR_HK and still calls payslip._sr_artikel14_hk(...), but models/hr_payslip.py no longer defines that method.

Practical meaning:

- Even though the core calculator was fixed, the module is not operationally clean.
- The repository still contains a broken path that should be expected to fail as soon as the stale view blocker is removed and the old rule path gets exercised.

### High-impact UI/data discrepancies

1. Contract preview debug HTML can disagree with sr_preview_netto because it rebuilds net with a different formula.
2. Payslip report still mixes up SR_KINDBIJ with actual child benefit.
3. Payslip report shows total gross/net values that can include components not listed in the visible rows.
4. Payslip report summary does not show aftrek_bv, so displayed rows do not fully reconcile to NET.
5. report_payslip_sr.xml header comments still describe a heffingskorting step that no longer exists in the core calculator.

### Documentation/config discrepancies

1. __manifest__.py still lists "Heffingskorting (SRD 750/maand)" as a supported calculation item.
2. views/sr_help_template.xml still teaches a user-visible heffingskorting flow.
3. views/hr_payroll_config_sr_views.xml still exposes HK as an Art. 14 parameter group.
4. controllers/main.py still ships SR_HEFFINGSKORTING_MAAND to the help frontend.

### Test/regression discrepancies

1. tests/test_improvements.py still calls payslip._sr_artikel14_hk().
2. No focused tests were found for:
   - Art. 17 combined bijzondere beloningen in one slip
   - Art. 17a output path
   - YTD cap across multiple payslips
   - full worked example from Loonbelasting context.md
   - report parity with actual payslip lines
3. The current test updates fix the old HK assumption in the main Art. 14 tests, but do not yet prove the risky new branches.

## Remaining Tasks

1. Remove sr_preview_hk_periode from views/hr_contract_views.xml and rerun module upgrade immediately.
2. Delete the remaining SR_HK salary rule from data/hr_salary_rule_data.xml and remove all remaining calls to _sr_artikel14_hk.
3. Decide whether SR_HEFFINGSKORTING_MAAND should be deleted, hidden, or explicitly deprecated. Right now it survives as a misleading config/documentation artifact.
4. Update controllers/main.py, views/sr_help_template.xml, views/hr_payroll_config_sr_views.xml, report_payslip_sr.xml comments, and __manifest__.py so the UI text matches the current calculator.
5. Refactor calc.generate_breakdown_html() so it does not recompute a separate preview net formula. Prefer passing the already computed preview totals into the HTML renderer.
6. Rebuild _get_sr_artikel14_breakdown() and report_payslip_sr.xml around actual payslip line_ids for both earnings and deductions, not a partial reconstructed subset.
7. Stop labeling SR_KINDBIJ as child benefit in the report path. Keep child benefit separate from generic contract vrijstellingen.
8. Add missing report rows for aftrek_bv and all positive earnings that currently affect NET but are not shown explicitly.
9. Make the YTD exemption lookup history-safe by reading prior applied exemption values instead of recomputing them from the current contract state.
10. Repair tests/test_improvements.py and add regression tests for:
    - exact worked example from the context document
    - combined Art. 17 bonus inputs
    - Art. 17a lump-sum taxation
    - YTD cap across multiple payslips
    - contract preview field vs debug HTML parity
    - payslip report parity vs actual NET and line_ids
11. After the above, rerun:

```powershell
Set-Location "C:\Program Files\Odoo 18.0e.20260407\server"
& "c:\Program Files\Odoo 18.0e.20260407\python\python.exe" odoo-bin -u l10n_sr_hr_payroll -d "Salarisverwerking-Module" --addons-path="c:\program files\odoo 18.0e.20260407\server\odoo\addons,c:\program files\odoo 18.0e.20260407\sessions\addons\18.0" --logfile= --stop-after-init --no-http
& "c:\Program Files\Odoo 18.0e.20260407\python\python.exe" odoo-bin --test-enable --test-tags=post_install_l10n -d "Salarisverwerking-Module" --addons-path="c:\program files\odoo 18.0e.20260407\server\odoo\addons,c:\program files\odoo 18.0e.20260407\sessions\addons\18.0" --logfile= --stop-after-init --no-http
```

## Final Conclusion

If the question is "were the earlier fixes implemented correctly?", the answer is:

- Core payroll tax logic: mostly yes.
- End-to-end module behavior, UI truthfulness, and regression safety: no, not yet.

The project is currently in a mixed state:

- the calculator and most special-tax rules moved in the right direction
- but the user-facing system still contains stale HK-era bindings, broken view references, misleading documentation, and incomplete report/test parity

So this should be treated as a partial fix set, not as a finished fiscally verified release.