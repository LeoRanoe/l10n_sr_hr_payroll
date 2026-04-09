# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrContractSrLine(models.Model):
    """
    Vaste loon regel op het contract — één rij per toelage of inhouding.

    De eindgebruiker beheert hier al zijn eigen debit/credit codes per werknemer:
      - Belastbaar  → telt mee in de Art. 14 loonbelastinggrondslag
      - Belastingvrij → Art. 10 WLB, geen loonbelasting/AOV
      - Inhouding   → netto aftrek (pensioenpremie, ziektekostenpremie, etc.)

    Voorbeelden:
      "Olie Toelage"       | SRD 500  | Belastbaar
      "Kleding Toelage"    | SRD 200  | Belastbaar
      "Kinderbijslag"      | SRD 500  | Belastingvrij
      "Transport"         | SRD 300  | Belastingvrij
      "Pensioenpremie"    | SRD 212  | Inhouding
      "Ziektekostenpremie"| SRD 100  | Inhouding
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
    name = fields.Char(
        string='Omschrijving',
        required=True,
        help='Naam van de toelage of inhouding, bijv. "Olie Toelage", "Pensioenpremie".',
    )
    currency_id = fields.Many2one(
        related='contract_id.currency_id',
        store=False,
    )
    amount = fields.Monetary(
        string='Bedrag per Periode',
        currency_field='currency_id',
        help='Vaste bedrag dat elke loonperiode verwerkt wordt.',
    )
    sr_categorie = fields.Selection(
        selection=[
            ('belastbaar', 'Belastbaar  (Art. 14 — LB + AOV grondslag)'),
            ('vrijgesteld', 'Belastingvrij  (Art. 10 — geen LB of AOV)'),
            ('inhouding', 'Inhouding / Aftrek  (netto aftrek)'),
        ],
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
