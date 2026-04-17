# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


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