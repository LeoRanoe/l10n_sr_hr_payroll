# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Tests voor de verbeteringen uit de 5-fasen implementatie:
  - @api.constrains percentage validatie (Fase 3)
  - sr_is_sr_struct computed boolean (Fase 5)
  - Calculator cache (Fase 4)
"""

from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestImprovements(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test Bedrijf Improvements',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Werknemer Impr',
            'company_id': cls.company.id,
        })
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

    def _create_contract(self, wage=5000, salary_type='monthly'):
        existing = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee.id),
            ('state', 'in', ('open', 'pending')),
        ])
        if existing:
            existing.write({'state': 'cancel'})
        return self.env['hr.contract'].create({
            'name': 'Test Contract Impr',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    # ── Fase 3: Percentage validatie ────────────────────────────────

    def test_percentage_zero_raises(self):
        """Een sr.line met amount_type='percentage' en percentage=0 moet een ValidationError geven."""
        contract = self._create_contract()
        with self.assertRaises(ValidationError):
            self.env['hr.contract.sr.line'].create({
                'contract_id': contract.id,
                'name': 'Test Percentage Nul',
                'sr_categorie': 'belastbaar',
                'amount_type': 'percentage',
                'percentage': 0.0,
            })

    def test_percentage_valid(self):
        """Een sr.line met amount_type='percentage' en percentage > 0 moet slagen."""
        contract = self._create_contract()
        line = self.env['hr.contract.sr.line'].create({
            'contract_id': contract.id,
            'name': 'Test Percentage Geldig',
            'sr_categorie': 'belastbaar',
            'amount_type': 'percentage',
            'percentage': 5.0,
        })
        self.assertTrue(line.id)

    def test_fixed_amount_no_percentage_check(self):
        """Een sr.line met amount_type='fixed' en percentage=0 mag geen fout geven."""
        contract = self._create_contract()
        line = self.env['hr.contract.sr.line'].create({
            'contract_id': contract.id,
            'name': 'Test Fixed',
            'sr_categorie': 'belastbaar',
            'amount_type': 'fixed',
            'amount': 100.0,
            'percentage': 0.0,
        })
        self.assertTrue(line.id)

    # ── Fase 5: sr_is_sr_struct boolean ─────────────────────────────

    def test_sr_is_sr_struct_true(self):
        """Payslip met SR structuur moet sr_is_sr_struct = True hebben."""
        contract = self._create_contract()
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Struct Check',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'company_id': self.company.id,
        })
        self.assertTrue(payslip.sr_is_sr_struct)

    def test_sr_is_sr_struct_false(self):
        """Payslip met andere structuur moet sr_is_sr_struct = False hebben."""
        contract = self._create_contract()
        # Gebruik de standaard 'Default Structure' of maak er een aan
        other_struct = self.env['hr.payroll.structure'].search([
            ('id', '!=', self.structure.id),
        ], limit=1)
        if not other_struct:
            self.skipTest("Geen andere structuur beschikbaar")
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Non-SR Struct',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': other_struct.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'company_id': self.company.id,
        })
        self.assertFalse(payslip.sr_is_sr_struct)

    # ── Fase 4: Calculator cache ────────────────────────────────────

    def test_calculator_cache_returns_consistent_results(self):
        """Meerdere aanroepen met dezelfde parameters moeten identieke resultaten geven."""
        contract = self._create_contract(wage=8000)
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Cache',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'company_id': self.company.id,
        })
        lb1 = payslip._sr_artikel14_lb(8000.0)
        hk1 = payslip._sr_artikel14_hk(8000.0)
        aov1 = payslip._sr_artikel14_aov(8000.0)
        lb2 = payslip._sr_artikel14_lb(8000.0)
        hk2 = payslip._sr_artikel14_hk(8000.0)
        aov2 = payslip._sr_artikel14_aov(8000.0)
        self.assertEqual(lb1, lb2, "LB moet consistent zijn bij herhaalde aanroep")
        self.assertEqual(hk1, hk2, "HK moet consistent zijn bij herhaalde aanroep")
        self.assertEqual(aov1, aov2, "AOV moet consistent zijn bij herhaalde aanroep")
