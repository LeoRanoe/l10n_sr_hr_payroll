# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_SR_SUPPORTED_CURRENCIES = frozenset({'SRD', 'USD', 'EUR'})

_SR_PAYSLIP_TEMPLATES = [
    ('odoo_standard', 'Odoo Standaard'),
    ('employee_simple', 'Klassiek (donkerblauw)'),
    ('compact', 'Compact Netto-overzicht'),
    ('artikel14_detail', 'Artikel 14 Detail'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    def init(self):
        """Migratie: initialiseer standaard contractvaluta, shortcut-weergave en loonstrook template voor bestaande bedrijven."""
        self.env.cr.execute("""
            UPDATE res_company c
            SET    sr_default_contract_currency_id = cur.id
            FROM   res_currency cur
            WHERE  cur.name = 'SRD'
              AND  c.sr_default_contract_currency_id IS NULL
        """)
        self.env.cr.execute("""
            UPDATE res_company
            SET    sr_show_contract_shortcuts = FALSE
            WHERE  sr_show_contract_shortcuts IS NULL
        """)
        self.env.cr.execute("""
            UPDATE res_company
            SET    sr_payslip_template = 'odoo_standard'
            WHERE  sr_payslip_template IS NULL
        """)

    sr_payslip_template = fields.Selection(
        selection=_SR_PAYSLIP_TEMPLATES,
        string='Standaard loonstrook template',
        default='odoo_standard',
        help=(
            'Welke templatestijl nieuwe loonstroken standaard gebruiken voor dit bedrijf. '
            '"Odoo Standaard" gebruikt Bootstrap-opmaak conform Odoo huisstijl met Surinaamse inhoud. '
            '"Klassiek" gebruikt de traditionele donkerblauwe SR-huisstijl. '
            'Per loonstrook kan de keuze nog worden overschreven.'
        ),
    )

    sr_default_contract_currency_id = fields.Many2one(
        'res.currency',
        string='Standaard Contractvaluta',
        domain=[('name', 'in', ['SRD', 'USD', 'EUR'])],
        default=lambda self: self.env['res.currency'].search([('name', '=', 'SRD')], limit=1),
        help=(
            'Standaard contractvaluta voor nieuwe SR-looncontracten in dit bedrijf. '
            'Kies SRD voor Surinaamse contracten, USD of EUR voor buitenlandse valutacontracten. '
            'Elke werknemer kan dit per contract aanpassen.'
        ),
    )
    sr_show_contract_shortcuts = fields.Boolean(
        string='Toon standaard contract-shortcuts',
        default=False,
        help=(
            'Toont een aparte shortcut-sectie op het contract voor de geselecteerde '
            'looncodetypes. Als dit uit staat, beheer je alle vaste toelagen en '
            'inhoudingen alleen via de tabel Vaste Loon Regels.'
        ),
    )
    sr_contract_shortcut_type_ids = fields.Many2many(
        'hr.contract.sr.line.type',
        'res_company_sr_shortcut_line_type_rel',
        'company_id',
        'line_type_id',
        string='Contract shortcut types',
        help=(
            'Bepaalt welke looncodetypes als snelle contract-shortcuts bovenaan het '
            'contractformulier verschijnen. Zo kan elk bedrijf zelf kiezen welke '
            'standaardposten apart zichtbaar moeten zijn.'
        ),
    )

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
