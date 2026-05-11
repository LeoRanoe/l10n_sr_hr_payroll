# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .sr_categorie import SR_CATEGORIE_BASE

_SR_LINE_SUPPORTED_CURRENCIES = frozenset({'SRD', 'USD', 'EUR'})


class HrContractSrLine(models.Model):
    """
    Vaste loon regel op het contract — één rij per toelage of inhouding.

    De eindgebruiker kiest een voorgedefinieerd type (hr.contract.sr.line.type)
    zodat naam en categorie automatisch worden ingevuld:
      - Belastbaar  → telt mee in de Art. 14 loonbelastinggrondslag
      - Belastingvrij → Art. 10 WLB, geen loonbelasting/AOV
            - Aftrek Belastingvrij → Art. 10f, verlaagt LB- en AOV-grondslag
            - Inhouding   → netto aftrek zonder effect op LB/AOV

    Elk vaste bedrag heeft een eigen line_currency_id (SRD, USD of EUR).
    Bij loonverwerking converteert de payroll-engine naar SRD via de bevroren
    wisselkoers op de loonstrook.  Bestaande records (aangemaakt vóór
    valuta-integratie) krijgen bij module-update automatisch SRD toegewezen.
    """
    _name = 'hr.contract.sr.line'
    _description = 'Suriname Vaste Loon Regel'
    _order = 'sr_categorie, sequence, id'

    def init(self):
        """Migratie: wijs SRD toe aan contractregels zonder lijn-valuta en normaliseer GENEESK naar fiscaal_grondslag."""
        self.env.cr.execute("""
            UPDATE hr_contract_sr_line l
            SET    line_currency_id = c.id
            FROM   res_currency c
            WHERE  c.name = 'SRD'
              AND  l.line_currency_id IS NULL
        """)
        # Normaliseer bestaande GENEESK-regels naar de nieuwe 'fiscaal_grondslag' categorie.
        self.env.cr.execute("""
            UPDATE hr_contract_sr_line l
            SET    sr_categorie = 'fiscaal_grondslag'
            FROM   hr_contract_sr_line_type t
            WHERE  l.type_id = t.id
              AND  t.code = 'GENEESK'
              AND  l.sr_categorie = 'belastbaar'
        """)

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
    line_currency_id = fields.Many2one(
        'res.currency',
        string='Valuta',
        domain=[('name', 'in', ['SRD', 'USD', 'EUR'])],
        store=True,
        required=True,
        default=lambda self: self.env['res.currency'].search([('name', '=', 'SRD')], limit=1),
        help=(
            'Valuta van dit vaste bedrag. Standaard gelijk aan de contractvaluta. '
            'Bij loonverwerking wordt een bedrag in USD of EUR omgerekend naar SRD '
            'via de bevroren wisselkoers op de loonstrook.'
        ),
    )
    currency_id = fields.Many2one(
        related='line_currency_id',
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
            '• Aftrek Belastingvrij: Art. 10f inhouding die zowel de '
            'LB- als AOV-grondslag verlaagt en daarnaast op netto wordt ingehouden.\n\n'
            '• Inhouding: wordt ingehouden op het nettoloon. '
            'Geen invloed op loonbelasting of AOV.\n\n'
            '• Fiscale Grondslag: voordeel in natura (bijv. VGB). Verhoogt de Art. 14 '
            'grondslag voor LB en AOV (via SR_VGB_BELAST), maar wordt NIET als cash '
            'uitbetaald op de loonstrook. Max gecapped op SR_VGB_MAX_JAAR.'
        ),
    )

    def _sr_effective_category(self):
        self.ensure_one()
        return self.type_id.sr_categorie or self.sr_categorie

    @api.onchange('type_id')
    def _onchange_type_id(self):
        """Vul naam en categorie automatisch in vanuit het gekozen type."""
        if self.type_id:
            self.name = self.type_id.name
            self.sr_categorie = self.type_id.sr_categorie

    @api.model
    def _sr_prepare_type_linked_vals(self, vals, existing=None):
        vals = self._sr_prepare_kindbijslag_vals(vals)

        type_id = vals.get('type_id')
        if type_id is None and existing:
            type_id = existing.type_id.id
        if not type_id:
            return vals

        line_type = self.env['hr.contract.sr.line.type'].browse(type_id).exists()
        if not line_type:
            return vals

        prepared = dict(vals)
        prepared['sr_categorie'] = line_type.sr_categorie
        if ('type_id' in prepared and 'name' not in prepared) or (existing is None and not prepared.get('name')):
            prepared['name'] = line_type.name
        return prepared

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

    @api.onchange('contract_id')
    def _onchange_contract_id_set_currency(self):
        """Synchroniseer line_currency_id met de contractvaluta bij aanmaken van nieuwe regels."""
        for line in self:
            if line.contract_id and line.contract_id.sr_contract_currency:
                line.line_currency_id = line.contract_id.sr_contract_currency
            elif not line.line_currency_id:
                line.line_currency_id = self.env['res.currency'].search(
                    [('name', '=', 'SRD')], limit=1
                )

    @api.model
    def _sr_default_line_currency_from_vals(self, vals):
        """Bepaal de standaard valuta voor een nieuw record op basis van het contract."""
        if vals.get('line_currency_id'):
            return vals
        contract_id = vals.get('contract_id')
        if not contract_id:
            return vals
        contract = self.env['hr.contract'].browse(contract_id).exists()
        if not contract:
            return vals
        sr_currency = contract.sr_contract_currency
        if sr_currency:
            vals = dict(vals)
            vals['line_currency_id'] = sr_currency.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sr_default_line_currency_from_vals(vals) for vals in vals_list]
        vals_list = [self._sr_prepare_type_linked_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if 'type_id' not in vals and 'sr_categorie' not in vals:
            return super().write(vals)

        result = True
        for line in self:
            line_vals = self._sr_prepare_type_linked_vals(vals, existing=line)
            result = super(HrContractSrLine, line).write(line_vals) and result
        return result

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

    @api.constrains('type_id', 'sr_categorie')
    def _check_type_category_consistency(self):
        for line in self:
            if line.type_id and line.sr_categorie != line.type_id.sr_categorie:
                raise ValidationError(
                    'Het gekozen contracttype bepaalt de fiscale categorie. '
                    'Pas het type aan of verwijder het type om de categorie handmatig te beheren.'
                )

    @api.constrains('line_currency_id', 'contract_id')
    def _check_line_currency_compatible(self):
        """
        Een lijn-valuta moet SRD zijn of gelijk aan de contractvaluta.
        EUR-lijnen op een USD-contract zijn niet toegestaan.
        """
        srd = self.env['res.currency'].search([('name', '=', 'SRD')], limit=1)
        for line in self:
            lc = line.line_currency_id
            if not lc:
                continue
            if lc.name not in _SR_LINE_SUPPORTED_CURRENCIES:
                raise ValidationError(
                    f'Lijn-valuta "{lc.name}" wordt niet ondersteund. Kies SRD, USD of EUR.'
                )
            contract_currency = line.contract_id.sr_contract_currency if line.contract_id else False
            if contract_currency and lc != srd and lc != contract_currency:
                raise ValidationError(
                    f'Lijn-valuta "{lc.name}" is niet compatibel met contractvaluta '
                    f'"{contract_currency.name}". Gebruik SRD of {contract_currency.name}.'
                )
