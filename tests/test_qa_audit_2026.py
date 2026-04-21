# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
QA regressietests voor de 2026 Suriname payroll uitbreiding.

Deze suite dekt drie auditdoelen:
  - persistence van werkboekingen, contractflags en settings
  - overwerkclassificatie vanuit work entries naar payslip inputs
  - 2026 fiscale regressies voor AKB, gratificatie en AOV franchise
"""

from datetime import date, datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged

from odoo.addons.l10n_sr_hr_payroll.models import sr_artikel14_calculator as calc


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestQAAudit2026(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['res.company'].create({
            'name': 'QA Audit Suriname Payroll 2026',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))

        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id
        cls.params = cls.env['ir.config_parameter'].sudo()

        cls.employee_monthly = cls.env['hr.employee'].create({
            'name': 'QA Monthly Werknemer',
            'company_id': cls.company.id,
        })
        cls.employee_fn = cls.env['hr.employee'].create({
            'name': 'QA FN Werknemer',
            'company_id': cls.company.id,
        })
        cls.employee_manager = cls.env['hr.employee'].create({
            'name': 'QA Manager Zonder OT',
            'company_id': cls.company.id,
        })
        cls.employee_akb = cls.env['hr.employee'].create({
            'name': 'QA AKB Werknemer',
            'company_id': cls.company.id,
        })
        cls.employee_grat_exact = cls.env['hr.employee'].create({
            'name': 'QA Gratificatie Exact',
            'company_id': cls.company.id,
        })
        cls.employee_grat_excess = cls.env['hr.employee'].create({
            'name': 'QA Gratificatie Overschot',
            'company_id': cls.company.id,
        })

        cls.normal_work_type = cls.env.ref(
            'hr_work_entry.work_entry_type_attendance', raise_if_not_found=False
        ) or cls.env['hr.work.entry.type'].search([], limit=1)
        if not cls.normal_work_type:
            cls.normal_work_type = cls.env['hr.work.entry.type'].create({
                'name': 'QA Aanwezigheid',
                'code': 'QAPRES',
            })

        cls.overtime_work_type = cls.normal_work_type.copy({
            'name': 'QA Overwerk',
            'code': 'QAOT',
            'sr_is_overtime': True,
            'sr_overtime_multiplier': 1.5,
        })

    def _create_contract(
        self,
        employee,
        wage=20000.0,
        salary_type='monthly',
        sr_has_overtime_right=True,
        sr_aantal_kinderen=0,
        sr_vaste_regels=None,
        date_start=date(2026, 1, 1),
    ):
        existing = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ('open', 'pending')),
        ])
        if existing:
            existing.write({'state': 'cancel'})

        return self.env['hr.contract'].create({
            'name': f'QA Contract {employee.name}',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_has_overtime_right': sr_has_overtime_right,
            'sr_aantal_kinderen': sr_aantal_kinderen,
            'sr_vaste_regels': sr_vaste_regels or [],
            'date_start': date_start,
            'state': 'open',
        })

    def _create_payslip(self, contract, date_from, date_to, inputs=None):
        payslip = self.env['hr.payslip'].create({
            'name': f'QA Loonstrook {contract.employee_id.name} {date_from}',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.company.id,
        })

        for input_ref, amount in inputs or []:
            input_type = self.env.ref(input_ref)
            self.env['hr.payslip.input'].create({
                'payslip_id': payslip.id,
                'name': input_type.name,
                'input_type_id': input_type.id,
                'amount': amount,
            })

        payslip.compute_sheet()
        return payslip

    def _create_work_entry(
        self,
        contract,
        work_entry_type,
        start_dt,
        hours,
        source='manual',
        batch=None,
        manual_override=False,
        state='validated',
    ):
        entry = self.env['hr.work.entry'].create({
            'name': f'{work_entry_type.name} {start_dt:%Y-%m-%d %H:%M}',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'work_entry_type_id': work_entry_type.id,
            'date_start': start_dt,
            'date_stop': start_dt + timedelta(hours=hours),
            'duration': hours,
            'state': 'draft',
            'sr_entry_source': source,
            'sr_import_batch': batch,
            'sr_manual_override': manual_override,
        })
        if state != 'draft':
            entry.write({'state': state})
        return entry

    def _line_total(self, payslip, code):
        return sum(payslip.line_ids.filtered(lambda line: line.code == code).mapped('total'))

    def _input_amount(self, payslip, xmlid):
        input_type = self.env.ref(xmlid)
        return sum(payslip.input_line_ids.filtered(
            lambda line: line.input_type_id == input_type
        ).mapped('amount'))

    def test_work_entry_changes_persist_in_postgresql(self):
        contract = self._create_contract(self.employee_monthly, wage=15000.0)
        entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 6, 18, 0, 0),
            2.0,
        )

        entry.write({
            'sr_overtime_150': 1.75,
            'sr_overtime_200': 0.25,
            'sr_entry_source': 'import',
            'sr_import_batch': 'QA-2026-IMPORT-001',
            'sr_manual_override': True,
        })

        self.env.cr.execute(
            """
            SELECT sr_overtime_150, sr_overtime_200, sr_entry_source, sr_import_batch, sr_manual_override
            FROM hr_work_entry
            WHERE id = %s
            """,
            (entry.id,),
        )
        row = self.env.cr.fetchone()

        self.assertAlmostEqual(float(row[0]), 1.75, places=2)
        self.assertAlmostEqual(float(row[1]), 0.25, places=2)
        self.assertEqual(row[2], 'import')
        self.assertEqual(row[3], 'QA-2026-IMPORT-001')
        self.assertTrue(row[4])

    def test_contract_overtime_flag_persists_in_postgresql(self):
        contract = self._create_contract(
            self.employee_manager,
            wage=24000.0,
            sr_has_overtime_right=False,
        )

        self.env.cr.execute(
            "SELECT sr_has_overtime_right FROM hr_contract WHERE id = %s",
            (contract.id,),
        )
        self.assertFalse(self.env.cr.fetchone()[0])

        contract.write({'sr_has_overtime_right': True})
        self.env.cr.execute(
            "SELECT sr_has_overtime_right FROM hr_contract WHERE id = %s",
            (contract.id,),
        )
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_settings_values_roundtrip_via_config_parameter(self):
        self.params.set_param('sr_payroll.akb_per_kind', 100.0)
        self.params.set_param('sr_payroll.overwerk_factor_150', 1.5)

        settings = self.env['res.config.settings'].create({})
        settings.write({
            'akb_per_kind': 250.0,
            'overwerk_factor_150': 1.75,
        })
        settings.set_values()

        self.env.registry.clear_cache()
        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = %s",
            ('sr_payroll.akb_per_kind',),
        )
        self.assertEqual(float(self.env.cr.fetchone()[0]), 250.0)

        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = %s",
            ('sr_payroll.overwerk_factor_150',),
        )
        self.assertEqual(float(self.env.cr.fetchone()[0]), 1.75)

        fresh_settings = self.env['res.config.settings'].create({})
        self.assertEqual(fresh_settings.akb_per_kind, 250.0)
        self.assertEqual(fresh_settings.overwerk_factor_150, 1.75)

    def test_monthly_work_entries_feed_150_percent_overtime_input(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=17333.3333,
            sr_has_overtime_right=True,
        )

        normal_entry = self._create_work_entry(
            contract,
            self.normal_work_type,
            datetime(2026, 4, 6, 8, 0, 0),
            8.0,
        )
        overtime_entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 6, 18, 0, 0),
            2.0,
        )

        self.assertAlmostEqual(normal_entry.sr_overtime_150, 0.0, places=2)
        self.assertAlmostEqual(normal_entry.sr_overtime_200, 0.0, places=2)
        self.assertAlmostEqual(overtime_entry.sr_overtime_150, 2.0, places=2)
        self.assertAlmostEqual(overtime_entry.sr_overtime_200, 0.0, places=2)

        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))
        expected_amount = 2.0 * payslip._sr_get_hourly_rate() * 1.5

        self.assertAlmostEqual(
            self._input_amount(payslip, 'l10n_sr_hr_payroll.sr_input_overwerk_150'),
            expected_amount,
            places=2,
        )
        self.assertAlmostEqual(
            self._input_amount(payslip, 'l10n_sr_hr_payroll.sr_input_overwerk_200'),
            0.0,
            places=2,
        )

    def test_fn_sunday_work_entry_generates_200_percent_overtime_input(self):
        contract = self._create_contract(
            self.employee_fn,
            wage=8000.0,
            salary_type='fn',
            sr_has_overtime_right=True,
        )
        overtime_entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 5, 9, 0, 0),
            4.0,
        )

        self.assertAlmostEqual(overtime_entry.sr_overtime_150, 0.0, places=2)
        self.assertAlmostEqual(overtime_entry.sr_overtime_200, 4.0, places=2)

        payslip = self._create_payslip(contract, date(2026, 3, 26), date(2026, 4, 8))
        expected_amount = 4.0 * payslip._sr_get_hourly_rate() * 2.0

        self.assertAlmostEqual(
            self._input_amount(payslip, 'l10n_sr_hr_payroll.sr_input_overwerk_200'),
            expected_amount,
            places=2,
        )
        self.assertAlmostEqual(
            self._input_amount(payslip, 'l10n_sr_hr_payroll.sr_input_overwerk_150'),
            0.0,
            places=2,
        )

    def test_no_overtime_right_blocks_generated_taxable_overtime_amount(self):
        contract = self._create_contract(
            self.employee_manager,
            wage=16000.0,
            sr_has_overtime_right=False,
        )
        overtime_entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 7, 18, 0, 0),
            4.0,
        )

        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))

        self.assertAlmostEqual(overtime_entry.sr_overtime_150, 4.0, places=2)
        self.assertAlmostEqual(
            self._input_amount(payslip, 'l10n_sr_hr_payroll.sr_input_overwerk_150'),
            0.0,
            places=2,
        )
        self.assertAlmostEqual(
            self._input_amount(payslip, 'l10n_sr_hr_payroll.sr_input_overwerk_200'),
            0.0,
            places=2,
        )
        self.assertAlmostEqual(self._line_total(payslip, 'GROSS'), 16000.0, places=2)

    def test_akb_is_capped_at_1000_and_more_than_four_children_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_contract(
                self.employee_akb,
                wage=20000.0,
                sr_aantal_kinderen=5,
            )

        contract = self._create_contract(
            self.employee_akb,
            wage=20000.0,
            sr_aantal_kinderen=4,
            sr_vaste_regels=[(0, 0, {
                'name': 'Kinderbijslag QA',
                'type_id': self.env.ref('l10n_sr_hr_payroll.sr_line_type_kinderbijslag').id,
                'sr_categorie': 'vrijgesteld',
                'amount': 1250.0,
            })],
        )
        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))

        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_VRIJ'), 1000.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_BELAST'), 250.0, places=2)

    def test_gratificatie_threshold_19500_only_taxes_the_excess(self):
        exact_contract = self._create_contract(self.employee_grat_exact, wage=20000.0)
        exact_slip = self._create_payslip(
            exact_contract,
            date(2026, 12, 1),
            date(2026, 12, 31),
            inputs=[('l10n_sr_hr_payroll.sr_input_gratificatie', 19500.0)],
        )
        self.assertAlmostEqual(exact_slip._sr_bijz_belastbaar_totaal(), 0.0, places=2)

        excess_contract = self._create_contract(self.employee_grat_excess, wage=20000.0)
        excess_slip = self._create_payslip(
            excess_contract,
            date(2026, 12, 1),
            date(2026, 12, 31),
            inputs=[('l10n_sr_hr_payroll.sr_input_gratificatie', 20000.0)],
        )
        self.assertAlmostEqual(excess_slip._sr_bijz_belastbaar_totaal(), 500.0, places=2)
        self.assertLess(self._line_total(excess_slip, 'SR_LB_BIJZ'), 0.0)

    def test_aov_franchise_applies_only_to_monthly_calculation(self):
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 4, 30))
        monthly = calc.calculate_lb(4000.0, 12, params)
        fortnight = calc.calculate_lb(4000.0, 26, params)

        self.assertEqual(monthly['franchise_periode'], 400.0)
        self.assertEqual(monthly['aov_grondslag'], 3600.0)
        self.assertEqual(monthly['aov_per_periode'], 144.0)

        self.assertEqual(fortnight['franchise_periode'], 0.0)
        self.assertEqual(fortnight['aov_grondslag'], 4000.0)
        self.assertEqual(fortnight['aov_per_periode'], 160.0)