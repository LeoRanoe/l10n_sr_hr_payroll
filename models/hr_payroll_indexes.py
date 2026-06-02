# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS hr_payslip_sr_struct_state_idx
                ON hr_payslip (sr_is_sr_struct, state)
            """
        )
        self.env.cr.execute(
            """
            WITH sr_structures AS (
                SELECT res_id
                  FROM ir_model_data
                 WHERE module = 'l10n_sr_hr_payroll'
                   AND model = 'hr.payroll.structure'
                   AND name IN ('sr_payroll_structure', 'sr_payroll_structure_hourly')
            )
            UPDATE hr_payslip AS hp
               SET sr_is_sr_struct = TRUE
              FROM sr_structures
             WHERE hp.struct_id = sr_structures.res_id
               AND COALESCE(hp.sr_is_sr_struct, FALSE) IS DISTINCT FROM TRUE
            """
        )


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS hr_payslip_line_slip_code_idx
                ON hr_payslip_line (slip_id, code)
            """
        )


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS hr_payslip_input_generated_idx
                ON hr_payslip_input (payslip_id, sr_generated_from_work_entry)
            """
        )


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS hr_work_entry_contract_state_dates_idx
                ON hr_work_entry (contract_id, state, date_start, date_stop)
            """
        )
