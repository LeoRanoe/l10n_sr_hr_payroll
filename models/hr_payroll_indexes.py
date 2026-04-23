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