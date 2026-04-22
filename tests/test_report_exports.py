# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import common, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestSrReportExports(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test SR Export Bedrijf',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))
        cls.job = cls.env['hr.job'].create({
            'name': 'Reporting Officer',
            'company_id': cls.company.id,
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Saphira Jones',
            'company_id': cls.company.id,
            'job_id': cls.job.id,
            'birthday': date(1984, 1, 23),
            'private_street': 'Bholaweg 4',
            'private_city': 'Paramaribo',
        })
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id
        cls.contract = cls.env['hr.contract'].create({
            'name': 'Export Testcontract',
            'employee_id': cls.employee.id,
            'company_id': cls.company.id,
            'structure_type_id': cls.structure_type.id,
            'wage': 18500.0,
            'sr_salary_type': 'monthly',
            'date_start': date(2025, 1, 1),
            'state': 'open',
        })

    def _make_done_sr_payslip(self, *, year=2026, month=8, payslip_run=None, inputs=None):
        payslip = self.env['hr.payslip'].create({
            'name': f'Export Testloonstrook {year}-{month}',
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'struct_id': self.structure.id,
            'date_from': date(year, month, 1),
            'date_to': date(year, month, 28),
            'company_id': self.company.id,
            'payslip_run_id': payslip_run.id if payslip_run else False,
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
        payslip.write({'state': 'done'})
        return payslip

    def test_batch_tax_overview_filtert_op_afgeronde_sr_loonstroken(self):
        payslip_run = self.env['hr.payslip.run'].create({
            'name': 'Batch Export Augustus 2026',
            'date_start': date(2026, 8, 1),
            'date_end': date(2026, 8, 31),
            'company_id': self.company.id,
        })
        done_slip = self._make_done_sr_payslip(payslip_run=payslip_run)
        draft_slip = self._make_done_sr_payslip(payslip_run=payslip_run, month=9)
        draft_slip.write({'state': 'draft'})

        eligible_slips = payslip_run._sr_get_tax_overview_slips()

        self.assertEqual(eligible_slips, done_slip)
        self.assertTrue(payslip_run.sr_has_sr_payslips)

    def test_batch_tax_overview_action_geeft_pdf_report(self):
        payslip_run = self.env['hr.payslip.run'].create({
            'name': 'Batch Export September 2026',
            'date_start': date(2026, 9, 1),
            'date_end': date(2026, 9, 30),
            'company_id': self.company.id,
        })
        self._make_done_sr_payslip(payslip_run=payslip_run, month=9)

        action = payslip_run.action_print_sr_tax_overview()

        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(action['report_name'], 'l10n_sr_hr_payroll.report_sr_tax_overview_period')

    def test_annual_statement_wizard_bouwt_jaardata(self):
        self._make_done_sr_payslip(year=2026, month=8)
        self._make_done_sr_payslip(year=2026, month=9)
        self._make_done_sr_payslip(year=2025, month=12)

        wizard = self.env['sr.payroll.annual.statement.wizard'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })
        data = wizard._get_sr_annual_statement_data()

        self.assertEqual(data['employee_name'], self.employee.name)
        self.assertEqual(data['year'], 2026)
        self.assertEqual(len(data['article14_rows']), 2)
        self.assertGreater(data['income_gross_total'], 0.0)
        self.assertGreaterEqual(data['lb_total'], 0.0)
        self.assertGreaterEqual(data['aov_total'], 0.0)

    def test_annual_statement_includes_overtime_tax_components_in_totals(self):
        payslip = self._make_done_sr_payslip(
            year=2026,
            month=11,
            inputs=[('l10n_sr_hr_payroll.sr_input_overwerk_150', 7600.0)],
        )
        wizard = self.env['sr.payroll.annual.statement.wizard'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })

        data = wizard._get_sr_annual_statement_data()
        breakdown = payslip._get_sr_artikel14_breakdown()
        expected_lb_total = (
            breakdown.get('lb_per_periode', 0.0)
            + breakdown.get('lb_bijz', 0.0)
            + breakdown.get('lb_17a', 0.0)
            + breakdown.get('lb_overwerk', 0.0)
        )
        expected_aov_total = (
            breakdown.get('aov_per_periode', 0.0)
            + breakdown.get('aov_bijz', 0.0)
            + breakdown.get('aov_17a', 0.0)
            + breakdown.get('aov_overwerk', 0.0)
        )

        self.assertTrue(any(row['article'] == 'art 17c' for row in data['article14_rows']))
        self.assertAlmostEqual(data['lb_total'], expected_lb_total, places=2)
        self.assertAlmostEqual(data['aov_total'], expected_aov_total, places=2)
        self.assertTrue(any(row['description'] == 'OVERWERK' for row in data['income_rows']))

    def test_annual_statement_action_geeft_pdf_report(self):
        self._make_done_sr_payslip(year=2026, month=10)
        wizard = self.env['sr.payroll.annual.statement.wizard'].create({
            'employee_id': self.employee.id,
            'year': 2026,
        })

        action = wizard.action_export_pdf()

        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(action['report_name'], 'l10n_sr_hr_payroll.report_sr_annual_statement')