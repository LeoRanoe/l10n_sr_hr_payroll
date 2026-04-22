# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_open_sr_annual_statement_wizard(self):
        self.ensure_one()
        return {
            'name': 'SR Jaaropgave',
            'type': 'ir.actions.act_window',
            'res_model': 'sr.payroll.annual.statement.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
                'default_year': fields.Date.context_today(self).year,
            },
        }