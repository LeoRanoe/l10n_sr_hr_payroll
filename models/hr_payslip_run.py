# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    sr_has_sr_payslips = fields.Boolean(
        string='Bevat SR-loonstroken',
        compute='_compute_sr_has_sr_payslips',
    )

    @api.depends('slip_ids', 'slip_ids.struct_id', 'slip_ids.state')
    def _compute_sr_has_sr_payslips(self):
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        for payslip_run in self:
            payslip_run.sr_has_sr_payslips = bool(
                sr_struct and payslip_run.slip_ids.filtered(lambda slip: slip.struct_id == sr_struct)
            )

    def _sr_get_tax_overview_slips(self):
        self.ensure_one()
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        return self.slip_ids.filtered(
            lambda slip: slip.struct_id == sr_struct and slip.state in ('done', 'paid')
        ).sorted(lambda slip: (
            slip.employee_id.department_id.name or '',
            slip.employee_id.name or '',
            slip.date_from or fields.Date.today(),
            slip.id,
        ))

    def action_print_sr_tax_overview(self):
        self.ensure_one()
        slips = self._sr_get_tax_overview_slips()
        if not slips:
            raise UserError(
                'Er zijn geen afgeronde SR-loonstroken in deze loonrun om een belastingoverzicht te exporteren.'
            )
        return self.env.ref('l10n_sr_hr_payroll.action_report_sr_tax_overview_period').report_action(self, config=False)