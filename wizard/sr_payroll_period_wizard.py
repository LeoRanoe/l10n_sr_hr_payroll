# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError


class SrPayrollPeriodWizard(models.TransientModel):
    _name = 'sr.payroll.period.wizard'
    _description = 'SR Periode Rapport Wizard'

    company_id = fields.Many2one(
        'res.company',
        string='Bedrijf',
        required=True,
        default=lambda self: self.env.company,
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Loonrun (Periode)',
        required=True,
        domain="[('company_id', '=', company_id), ('state', 'in', ['close', 'paid'])]",
    )
    run_name = fields.Char(related='payslip_run_id.name', string='Periode', readonly=True)
    date_from = fields.Date(related='payslip_run_id.date_start', string='Van', readonly=True)
    date_to = fields.Date(related='payslip_run_id.date_end', string='T/m', readonly=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.payslip_run_id and self.payslip_run_id.company_id != self.company_id:
            self.payslip_run_id = False

    def action_print_maandaangifte(self):
        self.ensure_one()
        if not self.payslip_run_id:
            raise UserError('Selecteer eerst een loonrun.')
        return self.payslip_run_id.action_print_sr_maandaangifte()

    def action_print_periode_overzicht(self):
        self.ensure_one()
        if not self.payslip_run_id:
            raise UserError('Selecteer eerst een loonrun.')
        return self.payslip_run_id.action_print_sr_company_period_overview()
