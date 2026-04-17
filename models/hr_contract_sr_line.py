# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .sr_categorie import SR_CATEGORIE_BASE


class HrContractSrLine(models.Model):
    """
    Vaste loon regel op het contract — één rij per toelage of inhouding.

    De eindgebruiker kiest een voorgedefinieerd type (hr.contract.sr.line.type)
    zodat naam en categorie automatisch worden ingevuld:
      - Belastbaar  → telt mee in de Art. 14 loonbelastinggrondslag
      - Belastingvrij → Art. 10 WLB, geen loonbelasting/AOV
      - Inhouding   → netto aftrek (pensioenpremie, ziektekostenpremie, etc.)
    """
    _name = 'hr.contract.sr.line'
    _description = 'Suriname Vaste Loon Regel'
    _order = 'sr_categorie, sequence, id'

    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        string='Volgorde',
        default=10,
    )
    type_id = fields.Many2one(
        'hr.contract.sr.line.type',
        string='Type',
        help='Selecteer een voorgedefinieerd type. Naam en categorie worden automatisch ingevuld.',
    )
    name = fields.Char(
        string='Omschrijving',
        required=True,
        help='Naam van de toelage of inhouding. Wordt automatisch ingevuld bij keuze van een type.',
    )
    currency_id = fields.Many2one(
        related='contract_id.currency_id',
        store=False,
    )
    amount = fields.Monetary(
        string='Bedrag per Periode',
        currency_field='currency_id',
        help='Vaste bedrag dat elke loonperiode verwerkt wordt (bij "Vast bedrag" type).',
    )
    amount_type = fields.Selection(
        selection=[
            ('fixed', 'Vast bedrag'),
            ('percentage', 'Percentage'),
        ],
        string='Berekeningswijze',
        default='fixed',
        required=True,
        help=(
            'Hoe het bedrag wordt bepaald:\n'
            '• Vast bedrag: bedrag per periode zoals ingevuld\n'
            '• Percentage: berekend percentage over de gekozen basis'
        ),
    )
    percentage = fields.Float(
        string='Percentage (%)',
        digits=(5, 2),
        help='Percentage dat berekend wordt over de gekozen basis.',
    )
    percentage_base = fields.Selection(
        selection=[
            ('basisloon', 'Basisloon (contract.wage)'),
            ('bruto_belastbaar', 'Bruto Belastbaar (basis + vaste belastbare toelagen)'),
        ],
        string='Percentage Basis',
        default='basisloon',
        help=(
            'Waarover het percentage berekend wordt:\n'
            '• Basisloon: alleen het bruto contractloon\n'
            '• Bruto Belastbaar: basisloon + vaste belastbare toelagen (vast bedrag)'
        ),
    )
    sr_categorie = fields.Selection(
        selection=SR_CATEGORIE_BASE,
        string='Categorie',
        required=True,
        default='belastbaar',
        help=(
            'Surinaamse loonbelastingcategorie:\n\n'
            '• Belastbaar: wordt opgeteld bij het belastbaar loon (Art. 14). '
            'LB en AOV worden hierover berekend.\n\n'
            '• Belastingvrij: wordt uitbetaald maar telt niet mee in de '
            'loonbelastinggrondslag (Art. 10 WLB).\n\n'
            '• Inhouding: wordt ingehouden op het nettoloon. '
            'Geen invloed op loonbelasting of AOV.'
        ),
    )

    @api.onchange('type_id')
    def _onchange_type_id(self):
        """Vul naam en categorie automatisch in vanuit het gekozen type."""
        if self.type_id:
            self.name = self.type_id.name
            self.sr_categorie = self.type_id.sr_categorie

    def _is_sr_kindbijslag_line(self):
        self.ensure_one()
        if self.type_id and self.type_id.code == 'KINDBIJ':
            return True
        return (self.name or '').strip().casefold() == 'kinderbijslag'

    @api.model
    def _sr_prepare_kindbijslag_vals(self, vals):
        name = (vals.get('name') or '').strip().casefold()
        if vals.get('type_id') or name != 'kinderbijslag':
            return vals
        if vals.get('sr_categorie') not in (False, None, 'vrijgesteld'):
            return vals
        kindbijslag_type = self.env.ref(
            'l10n_sr_hr_payroll.sr_line_type_kinderbijslag',
            raise_if_not_found=False,
        )
        if not kindbijslag_type:
            return vals
        vals = dict(vals)
        vals['type_id'] = kindbijslag_type.id
        vals['sr_categorie'] = kindbijslag_type.sr_categorie
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sr_prepare_kindbijslag_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        return super().write(self._sr_prepare_kindbijslag_vals(vals))

    @api.constrains('amount_type', 'percentage')
    def _check_percentage(self):
        for line in self:
            if line.amount_type == 'percentage' and line.percentage <= 0:
                raise ValidationError(
                    "Percentage moet groter dan 0 zijn wanneer de berekeningswijze 'Percentage' is."
                )

    @api.constrains('amount', 'amount_type')
    def _check_non_negative_amount(self):
        for line in self:
            if line.amount_type == 'fixed' and line.amount < 0:
                raise ValidationError(
                    'Negatieve vaste bedragen zijn niet toegestaan voor SR contractregels.'
                )

    @api.constrains('name', 'type_id', 'contract_id', 'sr_categorie')
    def _check_kindbijslag_configuration(self):
        for line in self:
            if not line._is_sr_kindbijslag_line():
                continue
            if line.contract_id and line.contract_id.sr_aantal_kinderen <= 0:
                raise ValidationError(
                    "Kinderbijslag vereist een positief 'Aantal Kinderen' op het contract."
                )
