# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SrPublicHoliday(models.Model):
    _name = 'sr.public.holiday'
    _description = 'Suriname Wettelijke Feestdag'
    _order = 'date'

    name = fields.Char(
        string='Naam',
        required=True,
    )
    date = fields.Date(
        string='Datum',
        required=True,
        index=True,
    )
    active = fields.Boolean(
        default=True,
        help='Niet-actieve feestdagen worden genegeerd bij overwerk-classificatie.',
    )

    _sql_constraints = [
        ('date_unique', 'UNIQUE(date)', 'Er bestaat al een feestdag op deze datum.'),
    ]
