# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrContract(models.Model):
    _inherit = 'hr.contract'

    sr_salary_type = fields.Selection(
        selection=[
            ('monthly', 'Maandloon (12× per jaar)'),
            ('fn', 'Fortnight Loon (26× per jaar)'),
        ],
        string='Surinaams Loontype',
        default='monthly',
        help='Selecteer het betaaltype: maandloon (12 periodes) of fortnight (26 periodes per jaar).',
    )
    sr_toelagen = fields.Monetary(
        string='Toelagen (Belastbaar)',
        currency_field='currency_id',
        default=0.0,
        help='Belastbare toelagen per loonperiode (bijv. vervoerskostenvergoeding die als loon belast wordt).',
    )
    sr_kinderbijslag = fields.Monetary(
        string='Kinderbijslag',
        currency_field='currency_id',
        default=0.0,
        help='Kinderbijslag per loonperiode — belastingvrij voordeel, wordt niet meegenomen in de loonbelastingberekening.',
    )
    sr_pensioenpremie = fields.Monetary(
        string='Pensioenpremie (werknemer)',
        currency_field='currency_id',
        default=0.0,
        help='Werknemerspremie pensioenfonds per loonperiode.',
    )
