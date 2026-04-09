# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrPayslipInputType(models.Model):
    """
    Uitbreiding van hr.payslip.input.type met een Surinaamse loonbelasting-categorie.

    De `sr_categorie` bepaalt hoe het bedrag wordt verwerkt in de salarisberekening:
    - belastbaar      → opgenomen in de loonbelastinggrondslag (Art. 14 WLB)
    - vrijgesteld     → uitbetaald maar niet belast (Art. 10 WLB)
    - inhouding       → ingehouden op het nettoloon
    - overwerk        → eigen Art. 17c belastingtarieven
    - vakantie        → belastingvrije vrijstelling Art. 10i, rest via Art. 17
    - gratificatie    → belastingvrije vrijstelling Art. 10j, rest via Art. 17
    - bijz_beloning   → bijzondere beloning Art. 17 (marginaal tarief methode)
    """
    _inherit = 'hr.payslip.input.type'

    sr_categorie = fields.Selection(
        selection=[
            ('belastbaar', 'Belastbare Toelage  (Art. 14 — opgenomen in LB-grondslag)'),
            ('vrijgesteld', 'Belastingvrije Toelage  (Art. 10 — niet in LB-grondslag)'),
            ('inhouding', 'Inhouding / Aftrek  (netto inhouding)'),
            ('overwerk', 'Overwerk  (Art. 17c — eigen belastingschijven)'),
            ('vakantie', 'Vakantietoelage  (Art. 10i — vrijstelling max SRD 10.016)'),
            ('gratificatie', 'Gratificatie / Bonus  (Art. 10j — vrijstelling max SRD 10.016)'),
            ('bijz_beloning', 'Bijzondere Beloning  (Art. 17 — marginaal tarief methode)'),
        ],
        string='SR Loon Categorie',
        default=False,
        help=(
            'Surinaamse loonbelastingcategorie. Bepaalt hoe dit bedrag in de loonstrook verwerkt wordt:\n\n'
            '• Belastbaar: telt mee in de Art. 14 grondslag — LB en AOV worden hier over berekend\n'
            '• Belastingvrij: wordt uitbetaald maar telt niet mee in de belastinggrondslag (Art. 10)\n'
            '• Inhouding: wordt ingehouden op het nettoloon (bijv. ziektekostenpremie extra)\n'
            '• Overwerk: eigen belastingschijven 5%/15%/25% conform Art. 17c\n'
            '• Vakantietoelage: vrijstelling = min(maandloon, SRD 10.016), rest belast via Art. 17\n'
            '• Gratificatie/Bonus: vrijstelling = min(maandloon, SRD 10.016), rest belast via Art. 17\n'
            '• Bijzondere Beloning: geen vaste vrijstelling, belast via marginaal tarief Art. 17'
        ),
    )
