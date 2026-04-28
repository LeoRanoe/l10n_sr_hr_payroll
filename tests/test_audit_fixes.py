# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tests import common, tagged

from ..models import sr_artikel14_calculator as calc


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestAuditFixes(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['res.company'].create({
            'name': 'Test Bedrijf SR Audit Fixes',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Audit Fix Werknemer',
            'company_id': cls.company.id,
        })
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id
        cls.hourly_structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure_hourly')
        cls.hourly_structure_type = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure_type_hourly')
        cls.kindbijslag_type = cls.env.ref('l10n_sr_hr_payroll.sr_line_type_kinderbijslag')
        cls.overwerk_input_type = cls.env.ref('l10n_sr_hr_payroll.sr_input_overwerk')
        cls.usd_currency = cls.env.ref('base.USD')

    def _make_contract(self, wage=20000.0, salary_type='monthly', sr_aantal_kinderen=0, sr_vaste_regels=None, structure_type=None, **extra_vals):
        vals = {
            'name': 'Audit Fix Contract',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': (structure_type or self.structure_type).id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_aantal_kinderen': sr_aantal_kinderen,
            'sr_vaste_regels': sr_vaste_regels or [],
            'date_start': date(2026, 1, 1),
            'state': 'open',
        }
        vals.update(extra_vals)
        return self.env['hr.contract'].create(vals)

    def _make_payslip(self, contract, structure=None):
        payslip = self.env['hr.payslip'].create({
            'name': 'Audit Fix Payslip',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': (structure or self.structure).id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        return payslip

    def _line_total(self, payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return line.total if line else 0.0

    def test_kinderbijslag_name_normalizes_to_type(self):
        contract = self._make_contract(
            sr_aantal_kinderen=4,
            sr_vaste_regels=[(0, 0, {
                'name': 'Kinderbijslag',
                'sr_categorie': 'vrijgesteld',
                'amount': 500.0,
            })],
        )

        line = contract.sr_vaste_regels
        self.assertEqual(line.type_id, self.kindbijslag_type)

        payslip = self._make_payslip(contract)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_VRIJ'), 500.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KINDBIJ'), 0.0, places=2)

    def test_kinderbijslag_requires_children(self):
        with self.assertRaises(ValidationError):
            self._make_contract(sr_vaste_regels=[(0, 0, {
                'name': 'Kinderbijslag',
                'sr_categorie': 'vrijgesteld',
                'amount': 125.0,
            })])

    def test_negative_contract_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_contract(sr_vaste_regels=[(0, 0, {
                'name': 'Transport',
                'sr_categorie': 'vrijgesteld',
                'amount': -10.0,
            })])

    def test_contract_rejects_negative_wage(self):
        with self.assertRaises(ValidationError):
            self._make_contract(wage=-1.0)

    def test_contract_rejects_more_than_four_children(self):
        with self.assertRaises(ValidationError):
            self._make_contract(sr_aantal_kinderen=5)

    def test_contract_onchange_caps_children_to_release_limit(self):
        contract = self.env['hr.contract'].new({'sr_aantal_kinderen': 10})

        warning = contract._onchange_sr_aantal_kinderen()

        self.assertEqual(contract.sr_aantal_kinderen, 4)
        self.assertIn('maximaal 4', warning['warning']['message'])

    def test_contract_onchange_resets_negative_wage(self):
        contract = self.env['hr.contract'].new({'wage': -500.0})

        warning = contract._onchange_wage_non_negative()

        self.assertEqual(contract.wage, 0.0)
        self.assertIn('Negatieve lonen', warning['warning']['message'])

    def test_2026_belastingvrij_parameter_defaults_to_zero(self):
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 5, 1))

        self.assertEqual(params['belastingvrij_jaar'], 0.0)
        self.assertEqual(
            calc.get_config_parameter_value(self.env, 'SR_BELASTINGVRIJ_JAAR'),
            0.0,
        )

    def test_contract_view_renders_wage_in_contract_currency(self):
        view = self.env.ref('l10n_sr_hr_payroll.hr_contract_sr_view_form')

        self.assertIn("options=\"{'currency_field': 'sr_contract_currency'}\"", view.arch_db)

    def test_foreign_currency_onchange_warns_with_exchange_rate_snapshot_context(self):
        contract = self.env['hr.contract'].new({
            'wage': 1500.0,
            'sr_contract_currency': self.usd_currency.id,
        })

        warning = contract._onchange_wage()

        self.assertTrue(warning)
        self.assertIn('36.5000', warning['warning']['message'])
        self.assertIn('sr_exchange_rate', warning['warning']['message'])

    def test_usd_preview_bruto_matches_rounded_payslip_basic(self):
        contract = self._make_contract(
            wage=123.456,
            sr_contract_currency=self.usd_currency.id,
        )

        payslip = self._make_payslip(contract)

        self.assertAlmostEqual(contract.sr_preview_bruto, self._line_total(payslip, 'BASIC'), places=2)

    def test_percentage_contract_rule_uses_srd_basis_for_foreign_currency(self):
        contract = self._make_contract(
            wage=100.0,
            sr_contract_currency=self.usd_currency.id,
            sr_vaste_regels=[(0, 0, {
                'name': '10% Toelage',
                'sr_categorie': 'belastbaar',
                'amount_type': 'percentage',
                'percentage': 10.0,
                'percentage_base': 'basisloon',
            })],
        )

        payslip = self._make_payslip(contract)

        self.assertAlmostEqual(self._line_total(payslip, 'SR_ALW'), 365.0, places=2)

    def test_gross_only_contains_basic_plus_taxable_contract_allowances(self):
        contract = self._make_contract(
            wage=20000.0,
            sr_aantal_kinderen=5,
            sr_vaste_regels=[
                (0, 0, {
                    'name': 'Belastbare Toelage',
                    'sr_categorie': 'belastbaar',
                    'amount': 300.0,
                }),
                (0, 0, {
                    'name': 'Kinderbijslag',
                    'type_id': self.kindbijslag_type.id,
                    'sr_categorie': 'vrijgesteld',
                    'amount': 1250.0,
                }),
            ],
        )

        payslip = self._make_payslip(contract)

        self.assertAlmostEqual(self._line_total(payslip, 'SR_ALW'), 300.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_BELAST'), 250.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'GROSS'), 20300.0, places=2)

    def test_contract_preview_lb_stays_aligned_with_gross_without_taxable_child_allowance(self):
        contract = self._make_contract(
            wage=20000.0,
            sr_aantal_kinderen=5,
            sr_vaste_regels=[
                (0, 0, {
                    'name': 'Belastbare Toelage',
                    'sr_categorie': 'belastbaar',
                    'amount': 300.0,
                }),
                (0, 0, {
                    'name': 'Kinderbijslag',
                    'type_id': self.kindbijslag_type.id,
                    'sr_categorie': 'vrijgesteld',
                    'amount': 1250.0,
                }),
            ],
        )

        payslip = self._make_payslip(contract)

        self.assertAlmostEqual(contract.sr_preview_lb_periode, abs(self._line_total(payslip, 'SR_LB')), places=2)

    def test_contract_preview_exposes_period_tax_base_after_forfaitaire(self):
        contract = self._make_contract(
            wage=20000.0,
            sr_vaste_regels=[(0, 0, {
                'name': 'Belastbare Toelage',
                'sr_categorie': 'belastbaar',
                'amount': 300.0,
            })],
        )

        payslip = self._make_payslip(contract)
        breakdown = payslip._get_sr_artikel14_breakdown()

        self.assertAlmostEqual(contract.sr_preview_belastinggrondslag, 19900.0, places=2)
        self.assertAlmostEqual(
            contract.sr_preview_belastinggrondslag,
            breakdown['grondslag_belasting_per_periode'],
            places=2,
        )

    def test_calculator_applies_heffingskorting_to_withheld_lb(self):
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 5, 1))

        result = calc.calculate_lb(10000.0, 12, params, heffingskorting_per_periode=750.0)

        self.assertAlmostEqual(result['lb_voor_heffingskorting_per_periode'], 1638.0, places=2)
        self.assertAlmostEqual(result['heffingskorting_per_periode'], 750.0, places=2)
        self.assertAlmostEqual(result['lb_per_periode'], 888.0, places=2)

    def test_contract_preview_lb_is_after_heffingskorting(self):
        contract = self._make_contract(wage=20255.60)
        payslip = self._make_payslip(contract)
        breakdown = payslip._get_sr_artikel14_breakdown()

        self.assertAlmostEqual(
            breakdown['lb_voor_heffingskorting_per_periode'],
            breakdown['lb_per_periode'] + breakdown['heffingskorting_per_periode'],
            places=2,
        )
        self.assertAlmostEqual(contract.sr_preview_lb_periode, abs(self._line_total(payslip, 'SR_LB')), places=2)
        self.assertAlmostEqual(contract.sr_preview_lb_periode, breakdown['lb_per_periode'], places=2)

    def test_preview_breakdown_aov_shows_aftrek_bv_before_franchise(self):
        contract = self._make_contract(
            wage=5000.0,
            sr_vaste_regels=[(0, 0, {
                'type_id': self.env.ref('l10n_sr_hr_payroll.sr_line_type_pensioen').id,
                'amount': 1000.0,
            })],
        )

        self.assertIn('Aftrek belastingvrij (Art. 10f)', contract.sr_preview_breakdown_html)
        self.assertIn('Belastbaar loon vóór franchise', contract.sr_preview_breakdown_html)
        self.assertIn('AOV inhouding per periode', contract.sr_preview_breakdown_html)

    def test_detailed_report_summary_no_longer_shows_heffingskorting_as_net_plus(self):
        report_view = self.env.ref('l10n_sr_hr_payroll.report_payslip_sr_detailed')

        self.assertNotIn('+ Heffingskorting', report_view.arch_db)
        self.assertIn('Aftrek belastingvrij (Art. 10f)', report_view.arch_db)

    def test_other_deductions_labels_are_generic_in_year_reports(self):
        annual_view = self.env.ref('l10n_sr_hr_payroll.report_sr_annual_statement')
        deduction_field = self.env['hr.payroll.tax.report']._fields['amount_pensioen_srd']

        self.assertIn('Andere Inhoudingen', annual_view.arch_db)
        self.assertIn('ANDERE INHOUDINGEN', annual_view.arch_db)
        self.assertEqual(deduction_field.string, 'Andere inhoudingen (SRD)')

    def test_payslip_summary_fields_are_stored_snapshots(self):
        payslip_model = self.env['hr.payslip']
        field_names = [
            'sr_bruto_totaal_display',
            'sr_heffingskorting_display',
            'sr_lb_totaal_display',
            'sr_aov_totaal_display',
            'sr_inhoudingen_totaal_display',
            'sr_netto_totaal_display',
        ]

        for field_name in field_names:
            self.assertTrue(payslip_model._fields[field_name].store, field_name)

    def test_negative_payslip_input_is_rejected(self):
        contract = self._make_contract()
        payslip = self.env['hr.payslip'].create({
            'name': 'Draft Audit Fix Payslip',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })

        with self.assertRaises(ValidationError):
            self.env['hr.payslip.input'].create({
                'payslip_id': payslip.id,
                'name': self.overwerk_input_type.name,
                'input_type_id': self.overwerk_input_type.id,
                'amount': -1.0,
            })

    def test_validated_overtime_work_entry_generates_input(self):
        contract = self._make_contract(wage=17333.3333)
        overtime_type = self.env['hr.work.entry.type'].create({
            'name': 'SR Overwerk 150%',
            'code': 'SR_OT_150_FIX',
            'country_id': self.env.ref('base.sr').id,
            'sr_is_overtime': True,
            'sr_overtime_multiplier': 1.5,
        })
        work_entry = self.env['hr.work.entry'].create({
            'name': 'Audit Fix Overwerk',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'work_entry_type_id': overtime_type.id,
            'date_start': datetime(2026, 5, 11, 18, 0, 0),
            'date_stop': datetime(2026, 5, 11, 20, 0, 0),
            'sr_manual_override': True,
        })
        self.assertTrue(work_entry.action_validate())

        payslip = self._make_payslip(contract)

        generated_inputs = payslip.input_line_ids.filtered('sr_generated_from_work_entry')
        self.assertEqual(len(generated_inputs), 1)
        self.assertAlmostEqual(generated_inputs.amount, 300.0, places=2)
        self.assertEqual(generated_inputs.sr_work_entry_id, work_entry)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_OVERWERK'), 300.0, places=2)

    def test_hourly_contract_overtime_work_entry_does_not_generate_input(self):
        contract = self._make_contract(
            wage=17333.3333,
            structure_type=self.hourly_structure_type,
        )
        overtime_type = self.env['hr.work.entry.type'].create({
            'name': 'SR Overwerk 150% Hourly',
            'code': 'SR_OT_150_HR',
            'country_id': self.env.ref('base.sr').id,
            'sr_is_overtime': True,
            'sr_overtime_multiplier': 1.5,
        })
        work_entry = self.env['hr.work.entry'].create({
            'name': 'Audit Fix Overwerk Hourly',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'work_entry_type_id': overtime_type.id,
            'date_start': datetime(2026, 5, 10, 18, 0, 0),
            'date_stop': datetime(2026, 5, 10, 20, 0, 0),
        })
        self.assertTrue(work_entry.action_validate())

        payslip = self._make_payslip(contract, structure=self.hourly_structure)

        generated_inputs = payslip.input_line_ids.filtered('sr_generated_from_work_entry')
        self.assertFalse(generated_inputs)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_OVERWERK'), 0.0, places=2)

    def test_regeneration_wizard_detects_overlapping_validated_entry(self):
        contract = self._make_contract()
        work_entry = self.env['hr.work.entry'].create({
            'name': 'Boundary Shift',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'date_start': datetime(2026, 4, 30, 22, 0, 0),
            'date_stop': datetime(2026, 5, 1, 2, 0, 0),
        })
        work_entry.action_validate()

        wizard = self.env['hr.work.entry.regeneration.wizard'].create({
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'employee_ids': [(6, 0, [contract.employee_id.id])],
        })

        self.assertIn(work_entry, wizard.validated_work_entry_ids)

    def test_force_regeneration_removes_overlapping_validated_entry(self):
        contract = self._make_contract()
        work_entry = self.env['hr.work.entry'].create({
            'name': 'Boundary Shift To Delete',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'date_start': datetime(2026, 4, 30, 22, 0, 0),
            'date_stop': datetime(2026, 5, 1, 2, 0, 0),
        })
        work_entry.action_validate()

        contract.generate_work_entries(date(2026, 5, 1), date(2026, 5, 31), force=True)

        self.assertFalse(work_entry.exists())

    def test_payroll_indexes_exist(self):
        index_names = {
            'hr_payslip_sr_struct_state_idx',
            'hr_payslip_line_slip_code_idx',
            'hr_work_entry_contract_state_dates_idx',
        }
        self.env.cr.execute(
            "SELECT indexname FROM pg_indexes WHERE indexname = ANY(%s)",
            (list(index_names),),
        )
        found = {row[0] for row in self.env.cr.fetchall()}
        self.assertTrue(index_names.issubset(found))

    def test_breakdown_uses_half_up_local_money_format(self):
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 5, 1))
        result = calc.calculate_lb(1234.555, 12, params)
        html = calc.generate_breakdown_html(
            result=result,
            wage=1234.555,
            periodes=12,
            salary_type='monthly',
        )

        self.assertEqual(result['bruto_per_periode'], 1234.56)
        self.assertIn('SRD 1.234,56', html)
        self.assertNotIn('1.234.56', html)

    def test_calculator_exposes_period_tax_base_after_forfaitaire(self):
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 5, 1))

        result = calc.calculate_lb(10000.0, 12, params)

        self.assertAlmostEqual(result['forfaitaire_per_periode'], 400.0, places=2)
        self.assertAlmostEqual(result['forfaitaire_max_per_periode'], 400.0, places=2)
        self.assertAlmostEqual(result['grondslag_belasting_per_periode'], 9600.0, places=2)
        self.assertAlmostEqual(result['grondslag_belasting_jaar'], 115200.0, places=2)

    def test_sr_payslip_rejects_period_spanning_contract_change(self):
        self._make_contract(
            salary_type='monthly',
            sr_vaste_regels=[(0, 0, {
                'name': 'Transport',
                'sr_categorie': 'vrijgesteld',
                'amount': 250.0,
            })],
        ).write({
            'date_end': date(2026, 5, 15),
            'state': 'close',
        })
        new_contract = self.env['hr.contract'].create({
            'name': 'Audit Fix Contract FN',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 20000.0,
            'sr_salary_type': 'fn',
            'date_start': date(2026, 5, 16),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'Spanning Contractwissel',
            'employee_id': new_contract.employee_id.id,
            'contract_id': new_contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })

        with self.assertRaises(UserError):
            payslip.compute_sheet()

    def test_settings_execute_persists_and_updates_akb_split(self):
        settings = self.env['res.config.settings'].create({})
        settings.write({
            'akb_per_kind': 100.0,
            'akb_max_bedrag': 300.0,
            'bijz_beloning_max': 19500.0,
        })
        settings.set_values()

        params = self.env['ir.config_parameter'].sudo()
        self.env.registry.clear_cache()
        self.assertEqual(float(params.get_param('sr_payroll.akb_per_kind')), 100.0)
        self.assertEqual(float(params.get_param('sr_payroll.akb_max_bedrag')), 300.0)

        akb_ref = self.env['hr.rule.parameter'].search([
            ('code', '=', 'SR_KINDBIJ_MAX_KIND_MAAND')
        ], limit=1)
        self.assertEqual(
            akb_ref.sr_current_value,
            '100.0',
            'Referentieparameterlijst moet de actuele settings-override tonen.',
        )

        contract = self._make_contract(
            sr_aantal_kinderen=4,
            sr_vaste_regels=[(0, 0, {
                'name': 'Kinderbijslag',
                'sr_categorie': 'vrijgesteld',
                'amount': 1000.0,
            })],
        )

        payslip = self._make_payslip(contract)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_VRIJ'), 300.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_BELAST'), 700.0, places=2)

    def test_current_reference_parameter_write_updates_live_setting(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('sr_payroll.akb_max_bedrag', 1000.0)

        parameter = self.env['hr.rule.parameter'].search([
            ('code', '=', 'SR_KINDBIJ_MAX_MAAND')
        ], limit=1)
        current_version = parameter.parameter_version_ids.filtered(
            lambda version: version.date_from and version.date_from <= date(2026, 4, 20)
        ).sorted(lambda version: version.date_from)[-1]

        current_version.write({'parameter_value': 300.0})

        self.env.registry.clear_cache()
        self.assertEqual(float(params.get_param('sr_payroll.akb_max_bedrag')), 300.0)
        self.assertEqual(parameter.sr_current_value, '300.0')

        contract = self._make_contract(
            sr_aantal_kinderen=4,
            sr_vaste_regels=[(0, 0, {
                'name': 'Kinderbijslag',
                'sr_categorie': 'vrijgesteld',
                'amount': 1000.0,
            })],
        )
        payslip = self._make_payslip(contract)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_VRIJ'), 300.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_BELAST'), 700.0, places=2)

    def test_future_reference_parameter_write_does_not_override_today(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('sr_payroll.akb_max_bedrag', 1000.0)

        parameter = self.env['hr.rule.parameter'].search([
            ('code', '=', 'SR_KINDBIJ_MAX_MAAND')
        ], limit=1)
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': parameter.id,
            'date_from': date(2027, 1, 1),
            'parameter_value': 1500.0,
        })

        self.env.registry.clear_cache()
        self.assertEqual(float(params.get_param('sr_payroll.akb_max_bedrag')), 1000.0)
        self.assertEqual(parameter.sr_current_value, '1000.0')

    def test_settings_default_values_match_2026_release(self):
        settings = self.env['res.config.settings'].create({})

        self.assertEqual(settings.akb_per_kind, 250.0)
        self.assertEqual(settings.akb_max_bedrag, 1000.0)
        self.assertEqual(settings.bijz_beloning_max, 19500.0)
        self.assertEqual(settings.aov_franchise_maand, 400.0)
        self.assertEqual(settings.heffingskorting, 750.0)

    def test_settings_reject_invalid_amount_and_rate_values(self):
        settings = self.env['res.config.settings'].create({})

        with self.assertRaises(ValidationError):
            settings.write({'akb_per_kind': -1.0})

        with self.assertRaises(ValidationError):
            settings.write({'tarief_1': 1.2})

        with self.assertRaises(ValidationError):
            settings.write({
                'schijf_1_grens': 50000.0,
                'schijf_2_grens': 40000.0,
                'schijf_3_grens': 126000.0,
            })