# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def action_open_sr_annual_statement_wizard(self):
        self.ensure_one()
        raise UserError('Jaaropgave valt buiten de basisloon-scope van deze modulevariant.')