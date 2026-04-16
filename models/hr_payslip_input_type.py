# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

from .sr_categorie import SR_CATEGORIE_EXTENDED


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
        selection=SR_CATEGORIE_EXTENDED,
        string='SR Loon Categorie',
        default=False,
        help=(
            'Surinaamse loonbelastingcategorie. Bepaalt hoe dit bedrag in de loonstrook verwerkt wordt:\n\n'
            '• Belastbaar: telt mee in de Art. 14 grondslag — LB en AOV worden hier over berekend\n'
            '• Belastingvrij: wordt uitbetaald maar telt niet mee in de belastinggrondslag (Art. 10)\n'
            '• Inhouding: wordt ingehouden op het nettoloon (bijv. ziektekostenpremie extra)\n'
            '• Overwerk: eigen belastingschijven 5%/15%/25% conform Art. 17c\n'
            '• Vakantietoelage: vrijstelling = min(maandloon, SR_BIJZ_VRIJSTELLING_MAX/jaar), rest belast via Art. 17\n'
            '• Gratificatie/Bonus: vrijstelling = min(maandloon, SR_BIJZ_VRIJSTELLING_MAX/jaar), rest belast via Art. 17\n'
            '  → Het vrijstellingsbedrag is configureerbaar via Payroll > Configuratie > SR Rule Parameters (SR_BIJZ_VRIJSTELLING_MAX)\n'
            '• Bijzondere Beloning: geen vaste vrijstelling, belast via marginaal tarief Art. 17'
        ),
    )
