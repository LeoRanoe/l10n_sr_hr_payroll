# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    sr_generated_from_work_entry = fields.Boolean(
        string='Gegenereerd uit Work Entry',
        default=False,
        readonly=True,
        help='Technische marker voor SR overtime-inputs die automatisch uit work entries zijn opgebouwd.',
    )
    sr_work_entry_id = fields.Many2one(
        'hr.work.entry',
        string='Bron Work Entry',
        readonly=True,
        ondelete='set null',
    )

    @api.constrains('amount', 'input_type_id')
    def _check_sr_non_negative_inputs(self):
        guarded_categories = {
            'belastbaar',
            'vrijgesteld',
            'inhouding',
            'overwerk',
            'vakantie',
            'gratificatie',
            'bijz_beloning',
            'uitkering_ineens',
        }
        for line in self:
            if line.input_type_id.sr_categorie in guarded_categories and line.amount < 0:
                raise ValidationError('Negatieve SR payslip-inputs zijn niet toegestaan.')