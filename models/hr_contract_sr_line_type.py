# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

from .sr_categorie import SR_CATEGORIE_BASE


class HrContractSrLineType(models.Model):
    """
    Voorgedefinieerde loon code types voor de Surinaamse salarisverwerking.

    Elk type definieert een vaste omschrijving en loonbelastingcategorie,
    zodat de eindgebruiker niet telkens opnieuw de naam moet typen.
    Voorbeelden: Olie Toelage, Pensioenpremie, Kinderbijslag.
    """
    _name = 'hr.contract.sr.line.type'
    _description = 'Suriname Vaste Loon Regel Type'
    _order = 'sr_categorie, sequence, name'

    name = fields.Char(
        string='Naam',
        required=True,
        help='Weergavenaam van het type, bijv. "Olie Toelage", "Pensioenpremie".',
    )
    code = fields.Char(
        string='Code',
        help='Korte interne code, bijv. "OLIE", "PENSIOEN". Optioneel.',
    )
    sr_categorie = fields.Selection(
        selection=SR_CATEGORIE_BASE,
        string='Categorie',
        required=True,
        default='belastbaar',
        help=(
            'Loonbelastingcategorie voor dit type:\n\n'
            '• Belastbaar: telt mee in de Art. 14 grondslag\n'
            '• Belastingvrij: Art. 10 WLB vrijstelling\n'
            '• Aftrek Belastingvrij: Art. 10f, verlaagt LB + AOV grondslag\n'
            '• Inhouding: netto aftrek zonder effect op LB/AOV'
        ),
    )
    description = fields.Text(
        string='Toelichting',
        help='Optionele toelichting voor de gebruiker.',
    )
    sequence = fields.Integer(
        string='Volgorde',
        default=10,
    )
    active = fields.Boolean(
        string='Actief',
        default=True,
        help='Deselecteer om dit type te archiveren zonder te verwijderen.',
    )
