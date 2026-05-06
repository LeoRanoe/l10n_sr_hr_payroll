# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_SR_SUPPORTED_CURRENCIES = frozenset({'SRD', 'USD', 'EUR'})


class ResCompany(models.Model):
    _inherit = 'res.company'

    sr_exchange_rate_usd = fields.Float(
        string='Dagkoers USD → SRD',
        digits=(16, 6),
        default=36.5,
        help=(
            'Actuele dagkoers: 1 USD = x SRD. Per bedrijf instelbaar. '
            'Wordt bij elke loonrun gekopieerd naar de loonstrook en daar bevroren opgeslagen. '
            'Pas de koers aan vóór elke loonrun als de wisselkoers gewijzigd is.'
        ),
    )
    sr_exchange_rate_eur = fields.Float(
        string='Dagkoers EUR → SRD',
        digits=(16, 6),
        default=39.0,
        help=(
            'Actuele dagkoers: 1 EUR = x SRD. Per bedrijf instelbaar. '
            'Wordt bij elke loonrun gekopieerd naar de loonstrook en daar bevroren opgeslagen. '
            'Pas de koers aan vóór elke loonrun als de wisselkoers gewijzigd is.'
        ),
    )

    @api.constrains('sr_exchange_rate_usd', 'sr_exchange_rate_eur')
    def _check_sr_exchange_rates_positive(self):
        for company in self:
            if company.sr_exchange_rate_usd <= 0:
                raise ValidationError(
                    'Dagkoers USD → SRD moet groter zijn dan 0. '
                    'Een nul- of negatieve koers blokkeert de loonverwerking.'
                )
            if company.sr_exchange_rate_eur <= 0:
                raise ValidationError(
                    'Dagkoers EUR → SRD moet groter zijn dan 0. '
                    'Een nul- of negatieve koers blokkeert de loonverwerking.'
                )
