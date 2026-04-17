# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    sr_is_overtime = fields.Boolean(
        string='SR Overwerk',
        help='Markeer dit type zodat gevalideerde work entries automatisch als SR overwerk naar de loonstrook worden doorgestuurd.',
    )
    sr_overtime_multiplier = fields.Float(
        string='SR Overwerkfactor',
        default=1.5,
        digits=(4, 2),
        help='Vermenigvuldigingsfactor voor het bruto uurloon, bijvoorbeeld 1.5, 2.0 of 3.25.',
    )

    @api.constrains('sr_is_overtime', 'sr_overtime_multiplier')
    def _check_sr_overtime_multiplier(self):
        for work_entry_type in self:
            if work_entry_type.sr_is_overtime and work_entry_type.sr_overtime_multiplier <= 0:
                raise ValidationError('De SR overwerkfactor moet groter zijn dan 0.')