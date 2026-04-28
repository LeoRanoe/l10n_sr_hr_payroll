# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
QA regressietests voor de 2026 Suriname payroll uitbreiding.

Deze suite dekt drie auditdoelen:
  - persistence van werkboekingen, contractflags en settings
  - overwerkclassificatie vanuit work entries naar payslip inputs
  - 2026 fiscale regressies voor AKB, gratificatie en AOV franchise
"""

from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET

from odoo.exceptions import UserError, ValidationError
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

        self.env.flush_all()

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

    def test_attendance_entry_auto_detects_extra_hours_against_schedule(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=18000.0,
            sr_has_overtime_right=True,
        )

        entry = self._create_work_entry(
            contract,
            self.normal_work_type,
            datetime(2026, 4, 7, 8, 0, 0),
            10.0,
        )

        expected_planned = 8.0
        if contract.resource_calendar_id:
            expected_planned = contract.resource_calendar_id.get_work_hours_count(
                datetime(2026, 4, 7, 8, 0, 0),
                datetime(2026, 4, 7, 18, 0, 0),
                compute_leaves=False,
            )
        expected_extra = max(10.0 - expected_planned, 0.0)

        self.assertAlmostEqual(entry.sr_planned_hours, expected_planned, places=2)
        self.assertAlmostEqual(entry.sr_extra_hours, expected_extra, places=2)
        self.assertAlmostEqual(entry.sr_overtime_150, expected_extra, places=2)
        self.assertAlmostEqual(entry.sr_overtime_200, 0.0, places=2)
        self.assertEqual(entry.sr_overtime_treatment, 'overtime_150')
        self.assertTrue(entry.sr_has_schedule_deviation)

    def test_extra_hours_without_overtime_right_stay_non_taxable(self):
        contract = self._create_contract(
            self.employee_manager,
            wage=18000.0,
            sr_has_overtime_right=False,
        )

        entry = self._create_work_entry(
            contract,
            self.normal_work_type,
            datetime(2026, 4, 7, 8, 0, 0),
            10.0,
        )

        expected_planned = 8.0
        if contract.resource_calendar_id:
            expected_planned = contract.resource_calendar_id.get_work_hours_count(
                datetime(2026, 4, 7, 8, 0, 0),
                datetime(2026, 4, 7, 18, 0, 0),
                compute_leaves=False,
            )
        expected_extra = max(10.0 - expected_planned, 0.0)

        self.assertAlmostEqual(entry.sr_extra_hours, expected_extra, places=2)
        self.assertAlmostEqual(entry.sr_overtime_150, 0.0, places=2)
        self.assertAlmostEqual(entry.sr_overtime_200, 0.0, places=2)
        self.assertEqual(entry.sr_overtime_treatment, 'unpaid')

        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))
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

    def test_manual_bucket_edit_auto_locks_classification(self):
        contract = self._create_contract(self.employee_monthly, wage=15000.0)
        entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 6, 18, 0, 0),
            2.0,
        )

        entry.write({'sr_overtime_150': 1.5})
        self.assertTrue(entry.sr_manual_override)
        self.assertEqual(entry.sr_overtime_treatment, 'manual')

    def test_contract_overtime_flag_persists_in_postgresql(self):
        contract = self._create_contract(
            self.employee_manager,
            wage=24000.0,
            sr_has_overtime_right=False,
        )

        self.env.flush_all()

        self.env.cr.execute(
            "SELECT sr_has_overtime_right FROM hr_contract WHERE id = %s",
            (contract.id,),
        )
        self.assertFalse(self.env.cr.fetchone()[0])

        contract.write({'sr_has_overtime_right': True})
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT sr_has_overtime_right FROM hr_contract WHERE id = %s",
            (contract.id,),
        )
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_contract_salary_type_persists_and_hourly_wage_recomputes_live(self):
        usd = self.env.ref('base.USD')
        old_rate = self.params.get_param('sr_payroll.exchange_rate_usd')

        try:
            self.params.set_param('sr_payroll.exchange_rate_usd', 36.5)
            contract = self._create_contract(
                self.employee_monthly,
                wage=100.0,
                salary_type='fn',
            )
            contract.write({'sr_contract_currency': usd.id})
            contract.invalidate_recordset(['sr_hourly_wage'])

            self.env.flush_all()
            self.env.cr.execute(
                "SELECT sr_salary_type FROM hr_contract WHERE id = %s",
                (contract.id,),
            )
            salary_type = self.env.cr.fetchone()[0]

            self.assertEqual(salary_type, 'fn')
            self.assertAlmostEqual(contract.sr_hourly_wage, 45.6250, places=4)

            contract.write({'sr_salary_type': 'monthly'})
            contract.invalidate_recordset(['sr_hourly_wage'])
            self.assertAlmostEqual(contract.sr_hourly_wage, 21.0577, places=4)

            self.params.set_param('sr_payroll.exchange_rate_usd', 40.0)
            contract.invalidate_recordset(['sr_hourly_wage'])
            self.assertAlmostEqual(contract.sr_hourly_wage, 23.0769, places=4)
        finally:
            if old_rate in (None, False, ''):
                self.params.search([('key', '=', 'sr_payroll.exchange_rate_usd')], limit=1).unlink()
            else:
                self.params.set_param('sr_payroll.exchange_rate_usd', old_rate)

    def test_batch_compute_sheet_keeps_overtime_inputs_per_slip(self):
        batch_employee = self.env['hr.employee'].create({
            'name': 'QA Batch OT Werknemer',
            'company_id': self.company.id,
        })
        contract = self._create_contract(
            self.employee_monthly,
            wage=17333.3333,
        )
        contract_b = self._create_contract(
            batch_employee,
            wage=17333.3333,
        )

        self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 7, 18, 0, 0),
            2.0,
        )
        self._create_work_entry(
            contract_b,
            self.overtime_work_type,
            datetime(2026, 4, 8, 18, 0, 0),
            1.0,
        )

        payslip_a = self.env['hr.payslip'].create({
            'name': 'QA Batch Slip A',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'company_id': self.company.id,
        })
        payslip_b = self.env['hr.payslip'].create({
            'name': 'QA Batch Slip B',
            'employee_id': contract_b.employee_id.id,
            'contract_id': contract_b.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'company_id': self.company.id,
        })

        (payslip_a | payslip_b).compute_sheet()

        self.assertAlmostEqual(
            self._input_amount(payslip_a, 'l10n_sr_hr_payroll.sr_input_overwerk_150'),
            300.0,
            places=2,
        )
        self.assertAlmostEqual(
            self._input_amount(payslip_b, 'l10n_sr_hr_payroll.sr_input_overwerk_150'),
            150.0,
            places=2,
        )

    def test_recompute_keeps_single_generated_input_and_frozen_exchange_rate(self):
        usd = self.env.ref('base.USD')
        old_rate = self.params.get_param('sr_payroll.exchange_rate_usd')
        try:
            self.params.set_param('sr_payroll.exchange_rate_usd', 36.5)
            contract = self._create_contract(
                self.employee_monthly,
                wage=100.0,
            )
            contract.write({'sr_contract_currency': usd.id})
            self._create_work_entry(
                contract,
                self.overtime_work_type,
                datetime(2026, 4, 7, 18, 0, 0),
                2.0,
            )

            payslip = self.env['hr.payslip'].create({
                'name': 'QA Recompute Snapshot',
                'employee_id': contract.employee_id.id,
                'contract_id': contract.id,
                'struct_id': self.structure.id,
                'date_from': date(2026, 4, 1),
                'date_to': date(2026, 4, 30),
                'company_id': self.company.id,
            })

            payslip.compute_sheet()
            generated_inputs = self.env['hr.payslip.input'].search([
                ('payslip_id', '=', payslip.id),
                ('sr_generated_from_work_entry', '=', True),
            ])
            initial_amount = sum(generated_inputs.mapped('amount'))
            self.assertAlmostEqual(payslip.sr_exchange_rate, 36.5, places=4)
            self.assertGreater(initial_amount, 0.0)
            self.assertEqual(len(generated_inputs), 1)

            self.params.set_param('sr_payroll.exchange_rate_usd', 40.0)
            payslip.compute_sheet()
            generated_inputs = self.env['hr.payslip.input'].search([
                ('payslip_id', '=', payslip.id),
                ('sr_generated_from_work_entry', '=', True),
            ])

            self.assertAlmostEqual(payslip.sr_exchange_rate, 36.5, places=4)
            self.assertAlmostEqual(
                sum(generated_inputs.mapped('amount')),
                initial_amount,
                places=2,
            )
            self.assertEqual(len(generated_inputs), 1)
        finally:
            if old_rate in (None, False, ''):
                self.params.search([('key', '=', 'sr_payroll.exchange_rate_usd')], limit=1).unlink()
            else:
                self.params.set_param('sr_payroll.exchange_rate_usd', old_rate)

    def test_named_contract_allowances_persist_via_contract_fields(self):
        contract = self._create_contract(
            self.employee_akb,
            wage=18000.0,
            sr_aantal_kinderen=2,
        )

        contract.write({
            'sr_kinderbijslag_bedrag': 500.0,
            'sr_vervoer_toelage': 350.0,
            'sr_representatie_toelage': 900.0,
            'sr_vrije_geneeskundige_behandeling': 125.0,
        })

        self.env.flush_all()

        self.env.cr.execute(
            """
            SELECT sr_kinderbijslag_bedrag, sr_vervoer_toelage, sr_representatie_toelage, sr_vrije_geneeskundige_behandeling
            FROM hr_contract
            WHERE id = %s
            """,
            (contract.id,),
        )
        row = self.env.cr.fetchone()
        self.assertEqual(tuple(float(value) for value in row), (500.0, 350.0, 900.0, 125.0))

        line_amounts = {
            line.type_id.code: line.amount
            for line in contract.sr_vaste_regels.sorted(lambda line: line.type_id.code)
        }
        self.assertEqual(line_amounts['KINDBIJ'], 500.0)
        self.assertEqual(line_amounts['TRANSPORT'], 350.0)
        self.assertEqual(line_amounts['REPRES'], 900.0)
        self.assertEqual(line_amounts['GENEESK'], 125.0)

        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))
        self.assertTrue(payslip)

        contract.invalidate_recordset(['sr_kinderbijslag_bedrag', 'sr_vervoer_toelage', 'sr_representatie_toelage', 'sr_vrije_geneeskundige_behandeling'])
        self.assertEqual(contract.sr_kinderbijslag_bedrag, 500.0)
        self.assertEqual(contract.sr_vervoer_toelage, 350.0)
        self.assertEqual(contract.sr_representatie_toelage, 900.0)
        self.assertEqual(contract.sr_vrije_geneeskundige_behandeling, 125.0)

    def test_named_contract_allowance_write_same_value_does_not_duplicate_rule_lines(self):
        contract = self._create_contract(
            self.employee_akb,
            wage=18000.0,
            sr_aantal_kinderen=2,
        )

        contract.write({'sr_kinderbijslag_bedrag': 500.0})
        first_line_ids = contract.sr_vaste_regels.filtered(lambda line: line.type_id.code == 'KINDBIJ').ids
        contract.write({'sr_kinderbijslag_bedrag': 500.0})
        second_line_ids = contract.sr_vaste_regels.filtered(lambda line: line.type_id.code == 'KINDBIJ').ids

        self.assertEqual(first_line_ids, second_line_ids)
        self.assertEqual(len(second_line_ids), 1)
        self.assertEqual(contract.sr_kinderbijslag_bedrag, 500.0)

    def test_work_entry_create_preclassifies_overtime_buckets(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=18000.0,
            sr_has_overtime_right=True,
        )

        work_entry = self.env['hr.work.entry'].create({
            'name': 'QA Preclassified Overtime',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'company_id': self.company.id,
            'work_entry_type_id': self.overtime_work_type.id,
            'date_start': datetime(2026, 4, 8, 18, 0, 0),
            'date_stop': datetime(2026, 4, 8, 20, 0, 0),
            'duration': 2.0,
        })

        self.assertAlmostEqual(work_entry.sr_overtime_150, 2.0, places=2)
        self.assertAlmostEqual(work_entry.sr_overtime_200, 0.0, places=2)

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

    def test_settings_default_get_prefers_saved_system_parameters(self):
        old_akb_value = self.params.get_param('sr_payroll.akb_per_kind')
        old_hk_value = self.params.get_param('sr_payroll.heffingskorting')
        try:
            self.params.set_param('sr_payroll.akb_per_kind', 325.0)
            self.params.set_param('sr_payroll.heffingskorting', 910.0)

            self.env.registry.clear_cache()
            values = self.env['res.config.settings'].default_get([
                'akb_per_kind',
                'heffingskorting',
            ])

            self.assertEqual(values['akb_per_kind'], 325.0)
            self.assertEqual(values['heffingskorting'], 910.0)
        finally:
            if old_akb_value in (None, False, ''):
                self.params.search([('key', '=', 'sr_payroll.akb_per_kind')], limit=1).unlink()
            else:
                self.params.set_param('sr_payroll.akb_per_kind', old_akb_value)
            if old_hk_value in (None, False, ''):
                self.params.search([('key', '=', 'sr_payroll.heffingskorting')], limit=1).unlink()
            else:
                self.params.set_param('sr_payroll.heffingskorting', old_hk_value)

    def test_settings_layout_key_migrates_from_legacy_config_parameter(self):
        legacy_key = 'sr_payroll.default_payslip_layout'
        new_key = 'sr_payroll.sr_default_payslip_layout'
        old_legacy_value = self.params.get_param(legacy_key)
        old_new_value = self.params.get_param(new_key)
        try:
            self.params.search([('key', '=', new_key)], limit=1).unlink()
            self.params.set_param(legacy_key, 'compact')

            settings = self.env['res.config.settings'].create({})
            self.assertEqual(settings.sr_default_payslip_layout, 'compact')

            settings.set_values()

            self.env.registry.clear_cache()
            self.assertEqual(self.params.get_param(new_key), 'compact')
            self.assertFalse(self.params.search([('key', '=', legacy_key)], limit=1))
        finally:
            new_param = self.params.search([('key', '=', new_key)], limit=1)
            legacy_param = self.params.search([('key', '=', legacy_key)], limit=1)
            if old_new_value in (None, False, ''):
                new_param.unlink()
            else:
                self.params.set_param(new_key, old_new_value)
            if old_legacy_value in (None, False, ''):
                legacy_param.unlink()
            else:
                self.params.set_param(legacy_key, old_legacy_value)

    def test_settings_field_config_keys_match_convention(self):
        settings_model = self.env['res.config.settings']
        expected_keys = {
            'sr_default_payslip_layout': 'sr_payroll.sr_default_payslip_layout',
            'belastingvrij_jaar': 'sr_payroll.belastingvrij_jaar',
            'forfaitaire_pct': 'sr_payroll.forfaitaire_pct',
            'forfaitaire_max_jaar': 'sr_payroll.forfaitaire_max_jaar',
            'schijf_1_grens': 'sr_payroll.schijf_1_grens',
            'schijf_2_grens': 'sr_payroll.schijf_2_grens',
            'schijf_3_grens': 'sr_payroll.schijf_3_grens',
            'tarief_1': 'sr_payroll.tarief_1',
            'tarief_2': 'sr_payroll.tarief_2',
            'tarief_3': 'sr_payroll.tarief_3',
            'tarief_4': 'sr_payroll.tarief_4',
            'heffingskorting': 'sr_payroll.heffingskorting',
            'aov_tarief': 'sr_payroll.aov_tarief',
            'aov_franchise_maand': 'sr_payroll.aov_franchise_maand',
            'bijz_beloning_max': 'sr_payroll.bijz_beloning_max',
            'akb_per_kind': 'sr_payroll.akb_per_kind',
            'akb_max_bedrag': 'sr_payroll.akb_max_bedrag',
            'overwerk_schijf_1_grens': 'sr_payroll.overwerk_schijf_1_grens',
            'overwerk_schijf_2_grens': 'sr_payroll.overwerk_schijf_2_grens',
            'overwerk_tarief_1': 'sr_payroll.overwerk_tarief_1',
            'overwerk_tarief_2': 'sr_payroll.overwerk_tarief_2',
            'overwerk_tarief_3': 'sr_payroll.overwerk_tarief_3',
            'overwerk_factor_150': 'sr_payroll.overwerk_factor_150',
            'overwerk_factor_200': 'sr_payroll.overwerk_factor_200',
        }

        for field_name, expected_key in expected_keys.items():
            self.assertEqual(settings_model._fields[field_name].config_parameter, expected_key)

    def test_settings_view_field_names_match_python_fields(self):
        expected_fields = {
            'belastingvrij_jaar',
            'forfaitaire_pct',
            'forfaitaire_max_jaar',
            'schijf_1_grens',
            'schijf_2_grens',
            'schijf_3_grens',
            'tarief_1',
            'tarief_2',
            'tarief_3',
            'tarief_4',
            'heffingskorting',
            'aov_tarief',
            'aov_franchise_maand',
            'bijz_beloning_max',
            'akb_per_kind',
            'akb_max_bedrag',
            'overwerk_schijf_1_grens',
            'overwerk_schijf_2_grens',
            'overwerk_tarief_1',
            'overwerk_tarief_2',
            'overwerk_tarief_3',
            'overwerk_factor_150',
            'overwerk_factor_200',
            'sr_default_payslip_layout',
        }
        view = self.env.ref('l10n_sr_hr_payroll.view_res_config_settings_sr_payroll')
        arch = ET.fromstring(view.arch_db)
        view_field_names = {
            node.get('name')
            for node in arch.findall('.//field')
            if node.get('name')
        }

        self.assertTrue(expected_fields.issubset(view_field_names))

    def test_monthly_work_entries_feed_150_percent_overtime_input(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=17333.3333,
            sr_has_overtime_right=True,
        )

        normal_entry = self._create_work_entry(
            contract,
            self.normal_work_type,
            datetime(2026, 4, 7, 8, 0, 0),
            8.0,
        )
        overtime_entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 7, 18, 0, 0),
            2.0,
        )

        expected_regular_overtime = max((normal_entry.duration or 0.0) - normal_entry.sr_planned_hours, 0.0)

        self.assertAlmostEqual(normal_entry.sr_overtime_150, expected_regular_overtime, places=2)
        self.assertAlmostEqual(normal_entry.sr_overtime_200, 0.0, places=2)
        self.assertAlmostEqual(overtime_entry.sr_overtime_150, 2.0, places=2)
        self.assertAlmostEqual(overtime_entry.sr_overtime_200, 0.0, places=2)

        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))
        expected_amount = (expected_regular_overtime + 2.0) * payslip._sr_get_hourly_rate() * 1.5

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

    def test_saved_overtime_multiplier_is_used_after_cache_clear(self):
        old_factor = self.params.get_param('sr_payroll.overwerk_factor_150')
        try:
            self.params.set_param('sr_payroll.overwerk_factor_150', 1.75)
            self.env.registry.clear_cache()

            contract = self._create_contract(
                self.employee_monthly,
                wage=17333.3333,
                sr_has_overtime_right=True,
            )
            self._create_work_entry(
                contract,
                self.overtime_work_type,
                datetime(2026, 4, 7, 18, 0, 0),
                2.0,
            )

            payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))
            expected_amount = float(payslip._sr_money_quantize(2.0 * payslip._sr_get_hourly_rate() * 1.75))

            self.assertAlmostEqual(
                self._input_amount(payslip, 'l10n_sr_hr_payroll.sr_input_overwerk_150'),
                expected_amount,
                places=2,
            )
        finally:
            if old_factor in (None, False, ''):
                self.params.search([('key', '=', 'sr_payroll.overwerk_factor_150')], limit=1).unlink()
            else:
                self.params.set_param('sr_payroll.overwerk_factor_150', old_factor)

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

        self.assertAlmostEqual(overtime_entry.sr_extra_hours, 4.0, places=2)
        self.assertAlmostEqual(overtime_entry.sr_overtime_150, 0.0, places=2)
        self.assertAlmostEqual(overtime_entry.sr_overtime_200, 0.0, places=2)
        self.assertEqual(overtime_entry.sr_overtime_treatment, 'unpaid')
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

    def test_akb_is_capped_at_four_children_without_blocking_contract_input(self):
        contract = self._create_contract(
            self.employee_akb,
            wage=20000.0,
            sr_aantal_kinderen=5,
            sr_vaste_regels=[(0, 0, {
                'name': 'Kinderbijslag QA',
                'type_id': self.env.ref('l10n_sr_hr_payroll.sr_line_type_kinderbijslag').id,
                'sr_categorie': 'vrijgesteld',
                'amount': 1250.0,
            })],
        )

        split = contract._sr_kinderbijslag_split(max_kind_maand=250.0, max_maand=5000.0)
        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))

        self.assertEqual(contract.sr_aantal_kinderen, 5)
        self.assertAlmostEqual(split['vrijgesteld'], 1000.0, places=2)
        self.assertAlmostEqual(split['belastbaar'], 250.0, places=2)
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

    def test_active_sr_contract_requires_positive_wage(self):
        with self.assertRaises(ValidationError):
            self._create_contract(
                self.employee_monthly,
                wage=0.0,
                sr_has_overtime_right=True,
            )

    def test_legacy_zero_wage_contract_blocks_payslip_compute(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=15000.0,
            sr_has_overtime_right=True,
        )
        self.env.cr.execute(
            "UPDATE hr_contract SET wage = %s WHERE id = %s",
            (0.0, contract.id),
        )
        self.env.invalidate_all()

        payslip = self.env['hr.payslip'].create({
            'name': 'QA Zero Wage Legacy',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'company_id': self.company.id,
        })

        with self.assertRaises(UserError):
            payslip.compute_sheet()

    def test_work_entry_rejects_more_than_24_hours_in_single_shift(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=18000.0,
            sr_has_overtime_right=True,
        )

        with self.assertRaises(ValidationError):
            self._create_work_entry(
                contract,
                self.normal_work_type,
                datetime(2026, 4, 7, 8, 0, 0),
                25.0,
            )

    def test_work_entry_hours_use_half_up_rounding_for_fiscal_snapshot(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=18000.0,
            sr_has_overtime_right=True,
        )
        entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 7, 18, 0, 0),
            1.005,
        )

        self.assertAlmostEqual(entry.sr_extra_hours, 1.01, places=2)
        self.assertAlmostEqual(entry.sr_overtime_150, 1.01, places=2)

    def test_batch_compute_sheet_keeps_live_2026_parameters_for_each_payslip(self):
        old_heffingskorting = self.params.get_param('sr_payroll.heffingskorting')
        try:
            self.params.set_param('sr_payroll.heffingskorting', 780.0)
            contract_a = self._create_contract(self.employee_monthly, wage=20000.0)
            contract_b = self._create_contract(self.employee_fn, wage=20000.0, salary_type='fn')
            slips = self.env['hr.payslip'].create([
                {
                    'name': 'QA Batch A',
                    'employee_id': contract_a.employee_id.id,
                    'contract_id': contract_a.id,
                    'struct_id': self.structure.id,
                    'date_from': date(2026, 4, 1),
                    'date_to': date(2026, 4, 30),
                    'company_id': self.company.id,
                },
                {
                    'name': 'QA Batch B',
                    'employee_id': contract_b.employee_id.id,
                    'contract_id': contract_b.id,
                    'struct_id': self.structure.id,
                    'date_from': date(2026, 3, 26),
                    'date_to': date(2026, 4, 8),
                    'company_id': self.company.id,
                },
            ])

            slips.compute_sheet()

            slip_a = slips.filtered(lambda slip: slip.contract_id == contract_a)
            slip_b = slips.filtered(lambda slip: slip.contract_id == contract_b)
            self.assertAlmostEqual(self._line_total(slip_a, 'SR_HK'), 780.0, places=2)
            self.assertAlmostEqual(self._line_total(slip_b, 'SR_HK'), 360.0, places=2)
        finally:
            if old_heffingskorting in (None, False, ''):
                self.params.search([('key', '=', 'sr_payroll.heffingskorting')], limit=1).unlink()
            else:
                self.params.set_param('sr_payroll.heffingskorting', old_heffingskorting)

    def test_overtime_salary_rules_use_article_17c_brackets(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=17333.3333,
            sr_has_overtime_right=True,
        )
        payslip = self._create_payslip(
            contract,
            date(2026, 4, 1),
            date(2026, 4, 30),
            inputs=[('l10n_sr_hr_payroll.sr_input_overwerk_150', 7600.0)],
        )

        self.assertAlmostEqual(self._line_total(payslip, 'SR_OVERWERK'), 7600.0, places=2)
        self.assertAlmostEqual(abs(self._line_total(payslip, 'SR_LB_OVERWERK')), 900.0, places=2)
        self.assertAlmostEqual(abs(self._line_total(payslip, 'SR_AOV_OVERWERK')), 304.0, places=2)

    def test_confirmed_payslip_recompute_is_blocked_to_preserve_persisted_lines(self):
        contract = self._create_contract(
            self.employee_monthly,
            wage=17333.3333,
            sr_has_overtime_right=True,
        )
        self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 7, 18, 0, 0),
            2.0,
        )
        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))
        frozen_lines = {line.code: line.total for line in payslip.line_ids}

        payslip.write({'state': 'done'})
        contract.write({'wage': 99999.0})

        with self.assertRaises(UserError):
            payslip.compute_sheet()

        payslip.invalidate_recordset(['line_ids'])
        self.assertEqual({line.code: line.total for line in payslip.line_ids}, frozen_lines)

    def test_release_ready_reference_scenario_matches_contract_hours_and_settings(self):
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 4, 30))
        contract = self._create_contract(
            self.employee_akb,
            wage=20255.60,
            sr_has_overtime_right=True,
            sr_aantal_kinderen=4,
            sr_vaste_regels=[
                (0, 0, {
                    'name': 'Representatie QA',
                    'sr_categorie': 'belastbaar',
                    'amount': 1300.0,
                }),
                (0, 0, {
                    'name': 'Kinderbijslag QA',
                    'type_id': self.env.ref('l10n_sr_hr_payroll.sr_line_type_kinderbijslag').id,
                    'sr_categorie': 'vrijgesteld',
                    'amount': 1250.0,
                }),
                (0, 0, {
                    'name': 'Pensioen QA',
                    'sr_categorie': 'aftrek_belastingvrij',
                    'amount': 212.50,
                }),
            ],
        )
        overtime_entry = self._create_work_entry(
            contract,
            self.overtime_work_type,
            datetime(2026, 4, 7, 18, 0, 0),
            2.0,
        )
        payslip = self._create_payslip(contract, date(2026, 4, 1), date(2026, 4, 30))
        breakdown = payslip._get_sr_artikel14_breakdown()

        expected_hourly = payslip._sr_get_hourly_rate()
        expected_overtime_gross = float(payslip._sr_money_quantize(2.0 * expected_hourly * 1.5))
        expected_overtime_lb = float(payslip._sr_money_quantize(expected_overtime_gross * 0.05))
        expected_overtime_aov = float(payslip._sr_money_quantize(expected_overtime_gross * 0.04))
        article14_result = calc.calculate_lb(
            20255.60 + 1300.0 + 250.0,
            12,
            params,
            aftrek_bv_per_periode=212.50,
            heffingskorting_per_periode=750.0,
        )
        expected_net = float(payslip._sr_money_quantize(
            20255.60 + 1300.0 + 1250.0 + expected_overtime_gross
            - article14_result['lb_per_periode']
            - article14_result['aov_per_periode']
            - 212.50
            - expected_overtime_lb
            - expected_overtime_aov
        ))

        self.assertAlmostEqual(overtime_entry.sr_overtime_150, 2.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_VRIJ'), 1000.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_KB_BELAST'), 250.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_OVERWERK'), expected_overtime_gross, places=2)
        self.assertAlmostEqual(abs(self._line_total(payslip, 'SR_LB_OVERWERK')), expected_overtime_lb, places=2)
        self.assertAlmostEqual(abs(self._line_total(payslip, 'SR_AOV_OVERWERK')), expected_overtime_aov, places=2)
        self.assertAlmostEqual(abs(self._line_total(payslip, 'SR_LB')), article14_result['lb_per_periode'], places=2)
        self.assertAlmostEqual(abs(self._line_total(payslip, 'SR_AOV')), article14_result['aov_per_periode'], places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'SR_HK'), 750.0, places=2)
        self.assertAlmostEqual(self._line_total(payslip, 'NET'), expected_net, places=2)
        self.assertAlmostEqual(breakdown['overtime_hours_150'], 2.0, places=2)
        self.assertAlmostEqual(breakdown['unpaid_extra_hours'], 0.0, places=2)
        self.assertTrue(breakdown['hours_summary_lines'])