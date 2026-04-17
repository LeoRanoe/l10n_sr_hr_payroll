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
        cls.kindbijslag_type = cls.env.ref('l10n_sr_hr_payroll.sr_line_type_kinderbijslag')
        cls.overwerk_input_type = cls.env.ref('l10n_sr_hr_payroll.sr_input_overwerk')

    def _make_contract(self, wage=20000.0, salary_type='monthly', sr_aantal_kinderen=0, sr_vaste_regels=None):
        return self.env['hr.contract'].create({
            'name': 'Audit Fix Contract',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_aantal_kinderen': sr_aantal_kinderen,
            'sr_vaste_regels': sr_vaste_regels or [],
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    def _make_payslip(self, contract):
        payslip = self.env['hr.payslip'].create({
            'name': 'Audit Fix Payslip',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
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
            'date_start': datetime(2026, 5, 10, 18, 0, 0),
            'date_stop': datetime(2026, 5, 10, 20, 0, 0),
        })
        self.assertTrue(work_entry.action_validate())

        payslip = self._make_payslip(contract)

        generated_inputs = payslip.input_line_ids.filtered('sr_generated_from_work_entry')
        self.assertEqual(len(generated_inputs), 1)
        self.assertAlmostEqual(generated_inputs.amount, 300.0, places=2)
        self.assertEqual(generated_inputs.sr_work_entry_id, work_entry)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_OVERWERK'), 300.0, places=2)

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